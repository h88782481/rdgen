#!/usr/bin/env python3
"""
rdpatch.py — 给 RustDesk 客户端源码打入「远程配置中心」和「隐藏连接窗口」补丁;启用自定义更新时,再补上 token 和更新入口。

在 rdgen 的 GitHub Actions 里运行:checkout 好 rustdesk 源码、跑完上游 allow_custom_update.py 之后执行。
定点正则替换,一套规则通配官方客户端 1.5.1+(含 nightly),不按版本分支;任一规则未命中即中止构建。

远程配置(始终应用):
  R1  启动拉取 + 后台刷新 -> fetch_remote_config(): global_init;
      Android/iOS 另在 start_server 入口拉取(开机服务不走 global_init)
  R2  隐藏层 host/key/api,且优先于 Windows exe license
  R3  加密落盘 last-good -> LocalConfig `_rdc`; persist 时也会 fetch

隐藏连接窗口(始终应用;allow-hide-cm=N 或非定制名客户端时不改变原有行为):
  H1  hide_cm() 只看 allow-hide-cm,不再要求仅密码接受 + 仅固定密码,临时密码也适用
  H2  隐藏时窗口不进任务栏;拿到 hide_cm 结果前先按隐藏处理,杜绝闪窗和残留任务栏按钮
  H3  有等待点击批准的连接时显示窗口(不进任务栏),批准后收起;密码接受的会话始终隐藏
  H4  设置页「安全」加回「隐藏连接管理窗口」勾选框(rdgen 写进默认设置,用户可取消)
  H5  Sciter(32 位)只能整窗隐藏,只在仅密码接受时隐藏,保证点击接受可用

自定义更新(RD_CUSTOM_UPDATE=true,即 rdgen 填了 update_public_key):
  更新检查地址、信任公钥、放开定制客户端检查更新由 allow_custom_update.py 完成,本脚本:
  U0  校验 Config Server 地址可用于更新,且 allow_custom_update.py 每处改动都已生效
      (它所在的 workflow 步骤 continue-on-error,失败不会中断构建)
  U1  版本检查、签名清单、安装包下载都带 Authorization: Bearer <token>
  U2  Flutter 定制客户端也显示更新提示(桌面首页卡片、Android 更新条)
  U3  浏览器下载按钮 -> <server>/download/<platform>

配置来自环境变量:
  RD_CONFIG_SERVER   自建服务器地址,例如 https://cfg.example.com  (必填)
  RD_CONFIG_TOKEN    客户端接口 Bearer token                        (必填)
  RD_CUSTOM_UPDATE   为 true 时应用 U0-U3

用法:
  RD_CONFIG_SERVER=https://cfg.example.com RD_CONFIG_TOKEN=xxx RD_CUSTOM_UPDATE=true python rdpatch.py [rustdesk_root]
"""
import os
import re
import sys
from urllib.parse import urlparse

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SERVER = os.environ.get("RD_CONFIG_SERVER", "").rstrip("/")
TOKEN = os.environ.get("RD_CONFIG_TOKEN", "")
CUSTOM_UPDATE = os.environ.get("RD_CUSTOM_UPDATE") == "true"

if not SERVER or not TOKEN:
    print("ERROR: RD_CONFIG_SERVER / RD_CONFIG_TOKEN must be set")
    sys.exit(2)

failed = []


def path_of(rel):
    return os.path.join(ROOT, *rel.split("/"))


def read(rel):
    with open(path_of(rel), encoding="utf-8") as f:
        return f.read()


def patch(rel, name, *rules, append=""):
    """依次应用 (pattern, repl) 规则,每条至少命中一次;append 追加到文件末尾。"""
    try:
        text = read(rel)
        for pattern, repl in rules:
            text, n = re.subn(pattern, repl, text)
            if not n:
                raise ValueError(f"pattern not found: {pattern[:80]}")
    except (OSError, ValueError) as e:
        print(f"[FAIL] {name} -> {rel}: {e}")
        failed.append(name)
        return
    with open(path_of(rel), "w", encoding="utf-8") as f:
        f.write(text + append)
    print(f"[ OK ] {name} -> {rel}")


def verify(rel, name, present=(), absent=()):
    """校验文件里应出现 / 不应再出现的片段。"""
    try:
        text = read(rel)
    except OSError as e:
        print(f"[FAIL] {name} -> {rel}: {e}")
        failed.append(name)
        return
    problems = [f"missing {s!r}" for s in present if s not in text]
    problems += [f"unexpected {s!r}" for s in absent if s in text]
    if problems:
        print(f"[FAIL] {name} -> {rel}: {'; '.join(problems)}")
        failed.append(name)
    else:
        print(f"[ OK ] {name} -> {rel}")


# --------------------------------------------------------------------------
# 远程配置
# --------------------------------------------------------------------------
# R2: 隐藏层 —— 下发的 key/api 只放在内存全局量里(不写 option,设置页不显示),
# 下发的 host/key/api 都优先于 Windows exe 文件名里的 license。
R2 = [
    # get_key: option("key") 为空时读下发的 key
    (
        r'    if key\.is_empty\(\) \{\n        key = config::RS_PUB_KEY\.to_owned\(\);\n    \}',
        "    if key.is_empty() {\n"
        "        let k = REMOTE_CFG_KEY.read().unwrap().clone();\n"
        "        if !k.is_empty() {\n"
        "            key = k;\n"
        "        }\n"
        "    }\n"
        "    if key.is_empty() {\n"
        "        key = config::RS_PUB_KEY.to_owned();\n"
        "    }",
    ),
    # get_api_server_: api option 为空时读下发的 api
    (
        r'    if !api\.is_empty\(\) \{\n        return api\.to_owned\(\);\n    \}',
        "    if !api.is_empty() {\n"
        "        return api.to_owned();\n"
        "    }\n"
        "    {\n"
        "        let a = REMOTE_CFG_API.read().unwrap().clone();\n"
        "        if !a.is_empty() {\n"
        "            return a;\n"
        "        }\n"
        "    }",
    ),
    # get_custom_rendezvous_server: 下发 host 优先于 license host=
    (
        r'pub fn get_custom_rendezvous_server\(custom: String\) -> String \{\n'
        r'    #\[cfg\(windows\)\]\n'
        r'    if let Ok\(lic\) = crate::platform::windows::get_license_from_exe_name\(\) \{\n'
        r'        if !lic\.host\.is_empty\(\) \{\n'
        r'            return lic\.host\.clone\(\);\n'
        r'        \}\n'
        r'    \}\n'
        r'    if !custom\.is_empty\(\) \{\n'
        r'        return custom;\n'
        r'    \}\n'
        r'    if !config::PROD_RENDEZVOUS_SERVER\.read\(\)\.unwrap\(\)\.is_empty\(\) \{\n'
        r'        return config::PROD_RENDEZVOUS_SERVER\.read\(\)\.unwrap\(\)\.clone\(\);\n'
        r'    \}\n'
        r'    ""\.to_owned\(\)\n'
        r'\}',
        "pub fn get_custom_rendezvous_server(custom: String) -> String {\n"
        "    if !custom.is_empty() {\n"
        "        return custom;\n"
        "    }\n"
        "    if !config::PROD_RENDEZVOUS_SERVER.read().unwrap().is_empty() {\n"
        "        return config::PROD_RENDEZVOUS_SERVER.read().unwrap().clone();\n"
        "    }\n"
        "    #[cfg(windows)]\n"
        "    if let Ok(lic) = crate::platform::windows::get_license_from_exe_name() {\n"
        "        if !lic.host.is_empty() {\n"
        "            return lic.host.clone();\n"
        "        }\n"
        "    }\n"
        "    \"\".to_owned()\n"
        "}",
    ),
    # get_rendezvous_server: license 不得盖掉已下发的 host
    (
        r'    #\[cfg\(windows\)\]\n'
        r'    if let Ok\(lic\) = crate::platform::get_license_from_exe_name\(\) \{\n'
        r'        if !lic\.host\.is_empty\(\) \{\n'
        r'            a = lic\.host;\n'
        r'        \}\n'
        r'    \}',
        "    #[cfg(windows)]\n"
        "    {\n"
        "        let prod = config::PROD_RENDEZVOUS_SERVER.read().unwrap().clone();\n"
        "        if !prod.is_empty() {\n"
        "            a = prod;\n"
        "        } else if let Ok(lic) = crate::platform::get_license_from_exe_name() {\n"
        "            if !lic.host.is_empty() {\n"
        "                a = lic.host;\n"
        "            }\n"
        "        }\n"
        "    }",
    ),
    # get_key: 下发 key 优先于 license / option
    (
        r'pub async fn get_key\(sync: bool\) -> String \{\n'
        r'    #\[cfg\(windows\)\]\n'
        r'    if let Ok\(lic\) = crate::platform::windows::get_license_from_exe_name\(\) \{\n'
        r'        if !lic\.key\.is_empty\(\) \{\n'
        r'            return lic\.key;\n'
        r'        \}\n'
        r'    \}',
        "pub async fn get_key(sync: bool) -> String {\n"
        "    {\n"
        "        let k = REMOTE_CFG_KEY.read().unwrap().clone();\n"
        "        if !k.is_empty() {\n"
        "            return k;\n"
        "        }\n"
        "    }\n"
        "    #[cfg(windows)]\n"
        "    if let Ok(lic) = crate::platform::windows::get_license_from_exe_name() {\n"
        "        if !lic.key.is_empty() {\n"
        "            return lic.key;\n"
        "        }\n"
        "    }",
    ),
    # get_api_server_: 下发 api 优先于 license
    (
        r'fn get_api_server_\(api: String, custom: String\) -> String \{\n'
        r'    #\[cfg\(windows\)\]\n'
        r'    if let Ok\(lic\) = crate::platform::windows::get_license_from_exe_name\(\) \{\n'
        r'        if !lic\.api\.is_empty\(\) \{\n'
        r'            return lic\.api\.clone\(\);\n'
        r'        \}\n'
        r'    \}',
        "fn get_api_server_(api: String, custom: String) -> String {\n"
        "    {\n"
        "        let a = REMOTE_CFG_API.read().unwrap().clone();\n"
        "        if !a.is_empty() {\n"
        "            return a;\n"
        "        }\n"
        "    }\n"
        "    #[cfg(windows)]\n"
        "    if let Ok(lic) = crate::platform::windows::get_license_from_exe_name() {\n"
        "        if !lic.api.is_empty() {\n"
        "            return lic.api.clone();\n"
        "        }\n"
        "    }",
    ),
]

# R3: load_custom_client 结束后把 last-good 写到正确的 APP_NAME 配置目录
R3 = [
    (
        r'        read_custom_client\(data\.trim\(\)\);\n        return;',
        "        read_custom_client(data.trim());\n"
        "        persist_remote_config_after_custom_client();\n"
        "        return;",
    ),
    (
        r'        read_custom_client\(&data\.trim\(\)\);\n    \}\n\}',
        "        read_custom_client(&data.trim());\n"
        "    }\n"
        "    persist_remote_config_after_custom_client();\n"
        "}",
    ),
]

REMOTE_CONFIG_BLOCK = f'''

// ==== injected by rdpatch.py: remote config center ====
pub const REMOTE_CONFIG_SERVER: &str = "{SERVER}";
pub const REMOTE_CONFIG_TOKEN: &str = "{TOKEN}";
pub const REMOTE_CONFIG_AUTH: &str = "Bearer {TOKEN}";

const REMOTE_CFG_CACHE_KEY: &str = "_rdc";
const REMOTE_CFG_REFRESH_INTERVAL: std::time::Duration = std::time::Duration::from_secs(60);

lazy_static::lazy_static! {{
    // Hidden layer: do NOT write option keys, so Settings UI won't show host/key/api
    // (same UX as compile-time sed constants). host -> PROD_RENDEZVOUS_SERVER;
    // key/api -> these globals, read by patched get_key / get_api_server_.
    static ref REMOTE_CFG_KEY: std::sync::RwLock<String> = Default::default();
    static ref REMOTE_CFG_API: std::sync::RwLock<String> = Default::default();
}}

static REMOTE_CFG_FETCH_OK: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);

/// Fetch host/key/api from self-hosted config server into the hidden layer.
/// Fetch synchronously before rendezvous, then refresh in one background thread per process.
/// At startup, fall back to last-good or compile-time defaults on failure.
/// Background failures keep the current config; unchanged values do not rewrite the cache.
/// NOTE: keep this block ASCII-only -- allowCustom.py must read common.rs as text on
/// Windows runners (default cp1252) without UnicodeDecodeError.
pub fn fetch_remote_config() {{
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| {{
        let _ = std::thread::spawn(|| {{
            do_fetch_remote_config();
        }})
        .join();
        std::thread::spawn(|| loop {{
            std::thread::sleep(REMOTE_CFG_REFRESH_INTERVAL);
            try_fetch_remote_config();
        }});
    }});
}}

fn remote_cfg_mix(data: &[u8]) -> Vec<u8> {{
    let t = REMOTE_CONFIG_TOKEN.as_bytes();
    if t.is_empty() {{
        return data.to_vec();
    }}
    data.iter()
        .enumerate()
        .map(|(i, b)| b ^ t[i % t.len()])
        .collect()
}}

fn enc_remote_cfg_blob(plain: &str) -> String {{
    let mixed = remote_cfg_mix(plain.as_bytes());
    let enc = hbb_common::password_security::encrypt_vec_or_original(&mixed, "00", 4096);
    String::from_utf8_lossy(&enc).to_string()
}}

fn dec_remote_cfg_blob(s: &str) -> String {{
    let (mixed, ok, _) =
        hbb_common::password_security::decrypt_vec_or_original(s.as_bytes(), "00");
    if !ok {{
        return String::new();
    }}
    String::from_utf8_lossy(&remote_cfg_mix(&mixed)).to_string()
}}

fn apply_hidden_remote_cfg(host: &str, key: &str, api: &str) -> bool {{
    let mut changed = false;
    for (target, value) in [
        (&*hbb_common::config::PROD_RENDEZVOUS_SERVER, host),
        (&*REMOTE_CFG_KEY, key),
        (&*REMOTE_CFG_API, api),
    ] {{
        if value.is_empty() {{
            continue;
        }}
        let mut current = target.write().unwrap();
        if *current != value {{
            *current = value.to_owned();
            changed = true;
        }}
    }}
    changed
}}

fn load_cached_remote_config() -> bool {{
    let enc = hbb_common::config::LocalConfig::get_option(REMOTE_CFG_CACHE_KEY);
    if enc.is_empty() {{
        return false;
    }}
    let plain = dec_remote_cfg_blob(&enc);
    if plain.is_empty() {{
        log::warn!("remote config cache decrypt failed");
        return false;
    }}
    let value: serde_json::Value = match serde_json::from_str(&plain) {{
        Ok(v) => v,
        Err(e) => {{
            log::warn!("remote config cache parse: {{e}}");
            return false;
        }}
    }};
    let host = value.get("h").and_then(|v| v.as_str()).unwrap_or("");
    let key = value.get("k").and_then(|v| v.as_str()).unwrap_or("");
    let api = value.get("a").and_then(|v| v.as_str()).unwrap_or("");
    if host.is_empty() && key.is_empty() && api.is_empty() {{
        return false;
    }}
    apply_hidden_remote_cfg(host, key, api);
    log::info!("remote config applied from encrypted local cache");
    true
}}

fn save_cached_remote_config() {{
    let host = hbb_common::config::PROD_RENDEZVOUS_SERVER
        .read()
        .unwrap()
        .clone();
    let key = REMOTE_CFG_KEY.read().unwrap().clone();
    let api = REMOTE_CFG_API.read().unwrap().clone();
    if host.is_empty() && key.is_empty() && api.is_empty() {{
        return;
    }}
    let plain = serde_json::json!({{"h": host, "k": key, "a": api}}).to_string();
    let enc = enc_remote_cfg_blob(&plain);
    if enc.is_empty() {{
        log::error!("remote config cache encrypt failed");
        return;
    }}
    hbb_common::config::LocalConfig::set_option(REMOTE_CFG_CACHE_KEY.to_owned(), enc);
}}

fn persist_remote_config_after_custom_client() {{
    // Android Flutter initialize: load_custom_client runs BEFORE
    // global_init / test_rendezvous. Fetch here so host/key/api are ready.
    fetch_remote_config();
    if REMOTE_CFG_FETCH_OK.load(std::sync::atomic::Ordering::SeqCst) {{
        save_cached_remote_config();
    }} else {{
        let _ = load_cached_remote_config();
    }}
}}

fn try_fetch_remote_config() -> bool {{
    let url = format!("{{}}/config", REMOTE_CONFIG_SERVER);
    let client = match reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(6))
        .build()
    {{
        Ok(c) => c,
        Err(e) => {{
            log::error!("fetch_remote_config build client: {{e}}");
            return false;
        }}
    }};
    let resp = match client
        .get(&url)
        .header("Authorization", REMOTE_CONFIG_AUTH)
        .send()
    {{
        Ok(r) => r,
        Err(e) => {{
            log::error!("fetch_remote_config request: {{e}}");
            return false;
        }}
    }};
    if !resp.status().is_success() {{
        log::error!("fetch_remote_config http {{}}", resp.status());
        return false;
    }}
    let value: serde_json::Value = match resp.json() {{
        Ok(v) => v,
        Err(e) => {{
            log::error!("fetch_remote_config parse: {{e}}");
            return false;
        }}
    }};
    let host = value.get("host").and_then(|v| v.as_str()).unwrap_or("");
    let key = value.get("key").and_then(|v| v.as_str()).unwrap_or("");
    let api = value.get("api").and_then(|v| v.as_str()).unwrap_or("");
    if host.is_empty() && key.is_empty() && api.is_empty() {{
        log::warn!("fetch_remote_config empty payload");
        return false;
    }}
    let changed = apply_hidden_remote_cfg(host, key, api);
    if !REMOTE_CFG_FETCH_OK.swap(true, std::sync::atomic::Ordering::SeqCst) || changed {{
        save_cached_remote_config();
        log::info!("remote config applied (hidden) from {{}}", REMOTE_CONFIG_SERVER);
    }}
    true
}}

fn do_fetch_remote_config() {{
    if try_fetch_remote_config() {{
        return;
    }}
    if load_cached_remote_config() {{
        return;
    }}
    log::warn!("remote config: http failed and no cache, using compile-time defaults");
}}
'''

patch(
    "src/common.rs",
    "R1-R3 remote config",
    (r"pub fn global_init\(\) -> bool \{\n", "pub fn global_init() -> bool {\n    fetch_remote_config();\n"),
    *R2,
    *R3,
    append=REMOTE_CONFIG_BLOCK,
)

# R1: Android/iOS start_server 入口拉配置。开机 MainService 只走这里,不经过 global_init / Flutter initialize。
# 桌面 start_server 签名不同,不会误打;函数体随版本增减,故只锚定签名、插在函数体最前。
patch(
    "src/server.rs",
    "R1 Android/iOS start_server fetch",
    (
        r'(#\[cfg\(any\(target_os = "android", target_os = "ios"\)\)\]\n'
        r'#\[tokio::main\]\n'
        r'pub async fn start_server\(_is_server: bool\) \{\n)',
        r"\1    crate::common::fetch_remote_config();\n",
    ),
)


# --------------------------------------------------------------------------
# 隐藏连接窗口
# --------------------------------------------------------------------------
# 只有 pro / 定制名客户端能隐藏,ipc.rs 里这道门槛不能放开:非定制客户端取消勾选写的是空值,
# 会回落到默认的 Y,关不掉。
patch(
    "libs/hbb_common/src/password_security.rs",
    "H1 hide_cm only checks allow-hide-cm",
    (
        r"(pub fn hide_cm\(\) -> bool \{\n)"
        r"    approve_mode\(\) == ApproveMode::Password\n"
        r"        && verification_method\(\) == VerificationMethod::OnlyUsePermanentPassword\n"
        r"        && ",
        r"\1    ",
    ),
)

# H2: 启动到 cmGetConfig 返回之间到达的连接会把窗口顶到前台,所以先按隐藏处理。
# setSkipTaskbar 要放在 waitUntilReadyToShow 之后,后者会按 WindowOptions 把它重设为 false。
patch(
    "flutter/lib/main.dart",
    "H2 cm window off taskbar, hidden until hide_cm known",
    (
        r"(void runConnectionManagerScreen\(\) async \{\n  await initEnv\(kAppTypeConnectionManager\);\n)",
        r"\1  gFFI.serverModel.hideCm = true;\n",
    ),
    (
        r"(    await windowManager\.waitUntilReadyToShow\(windowOptions, null\);\n)"
        r"(    bind\.mainHideDock\(\);\n    await windowManager\.minimize\(\);\n)",
        r"\1    await windowManager.setSkipTaskbar(true);\n\2",
    ),
)

# H3: 密码接受的连接到达时已授权,不会挂起,所以仅密码 / 临时密码时窗口始终隐藏;
# 批准后由 500ms 定时器收起。
patch(
    "flutter/lib/models/server_model.dart",
    "H3 show cm only while a client awaits approval",
    (
        r"(  List<Client> get clients => _clients;\n)",
        r"\1\n  bool get _hasPendingClient =>\n"
        r"      _clients.any((client) => !client.authorized && !client.disconnected);\n",
    ),
    (
        r"(            _zeroClientLengthCounter = 0;\n)            if \(!hideCm\) showCmWindow\(\);",
        r"\1            if (!hideCm || _hasPendingClient) {\n"
        r"              showCmWindow();\n"
        r"            } else {\n"
        r"              hideCmWindow();\n"
        r"            }",
    ),
    (
        r"      \} else if \(!hideCm\) \{\n        showCmWindow\(\);\n      \}",
        r"      } else if (!hideCm || _hasPendingClient) {\n"
        r"        showCmWindow();\n"
        r"      } else {\n"
        r"        hideCmWindow();\n"
        r"      }",
    ),
    (
        r"desktopType == DesktopType\.cm && !hideCm\)",
        r"desktopType == DesktopType.cm && (!hideCm || _hasPendingClient))",
    ),
)

patch(
    "flutter/lib/desktop/pages/desktop_setting_page.dart",
    "H4 hide cm checkbox",
    (
        r"(            'allow-only-conn-window-open',\n"
        r"            reverse: false, enabled: enabled\),\n)",
        r"\1      if (bind.isCustomClient())\n"
        r"        _OptionCheckBox(context, 'Hide connection management window',\n"
        r"            'allow-hide-cm',\n"
        r"            enabled: enabled),\n",
    ),
)

patch(
    "src/ui.rs",
    "H5 sciter cm hides only in password approve mode",
    (
        r'(\*cm::HIDE_CM\.lock\(\)\.unwrap\(\) = crate::ipc::get_config\("hide_cm"\)\n'
        r"            \.ok\(\)\n"
        r"            \.flatten\(\)\n"
        r"            \.unwrap_or_default\(\)\n"
        r'            == "true");',
        r"\1\n            && hbb_common::password_security::approve_mode()\n"
        r"                == hbb_common::password_security::ApproveMode::Password;",
    ),
)


# --------------------------------------------------------------------------
# 自定义更新
# --------------------------------------------------------------------------
if CUSTOM_UPDATE:
    # U0: 客户端只接受 https、不带端口的更新地址,并按它校验清单里的安装包地址。
    url = urlparse(SERVER)
    if url.scheme != "https" or url.netloc != url.hostname or url.path or url.query or url.fragment:
        print(f"[FAIL] U0 RD_CONFIG_SERVER must be https://<lowercase domain> without port or path: {SERVER}")
        failed.append("U0 config server url")
    verify(
        "libs/hbb_common/src/lib.rs",
        "U0 allow_custom_update: update url, build number",
        present=[f'"{SERVER}/api/version/latest"', "v.split_once('+')"],
    )
    verify(
        "src/common.rs",
        "U0 allow_custom_update: custom client check, release url",
        present=["display_version.split_once('+')"],
        absent=[
            "pub fn check_software_update() {\n    if is_custom_client() {",
            'url.host_str() != Some("github.com")',
        ],
    )
    verify(
        "src/updater/artifact.rs",
        "U0 allow_custom_update: artifact url",
        present=[f'format!("{SERVER}/rustdesk/rustdesk/releases/download/{{release_id}}/")'],
        absent=['parsed.host_str() != Some("github.com")'],
    )
    verify(
        "src/update_metadata.rs",
        "U0 allow_custom_update: trusted key",
        present=['key_id: "custom-update"'],
    )

    # U1: 版本检查(Rustls 与 NativeTls 重试两处)、签名清单、安装包下载都带 token
    AUTH = '.header("Authorization", crate::common::REMOTE_CONFIG_AUTH)'
    patch(
        "src/common.rs",
        "U1 version check token",
        (r"\.post\(&url\)\s*\.json\(&request\)", f".post(&url){AUTH}.json(&request)"),
    )
    patch(
        "src/updater/artifact.rs",
        "U1 update metadata token",
        (
            r"\.get\(url\)(\s*)\.timeout\(UPDATE_SIDECAR_HTTP_REQUEST_TIMEOUT\)",
            rf".get(url)\1{AUTH}\1.timeout(UPDATE_SIDECAR_HTTP_REQUEST_TIMEOUT)",
        ),
    )
    patch(
        "src/updater/download.rs",
        "U1 update package token",
        (r"client\.get\(download_url\)\.send\(\)", f"client.get(download_url){AUTH}.send()"),
    )

    # U2 / U3: Flutter 定制客户端也检查并提示更新;「下载」打开 config server 的下载跳转
    patch(
        "flutter/lib/common.dart",
        "U2 check update",
        (r"if \(!isWeb\) \{\n(\s*)if \(!bind\.isCustomClient\(\)\) \{", r"if (!isWeb) {\n\1if (true) {"),
    )
    patch(
        "flutter/lib/desktop/pages/desktop_home_page.dart",
        "U2/U3 desktop update card",
        (
            r"if \(!bind\.isCustomClient\(\) &&\s*updateUrl\.isNotEmpty &&\s*!isCardClosed &&\s*"
            r"bind\.mainUriPrefixSync\(\)\.contains\('rustdesk'\)\) \{",
            "if (updateUrl.isNotEmpty && !isCardClosed) {",
        ),
        (
            r"final Uri url = Uri\.parse\('[^']*'\);",
            f"final Uri url = Uri.parse('{SERVER}/download/${{isWindows ? 'windows' : isMacOS ? 'macos' : 'linux'}}');",
        ),
    )
    patch(
        "flutter/lib/mobile/pages/connection_page.dart",
        "U2/U3 android update bar",
        (r"if \(!bind\.isCustomClient\(\) && !isIOS\)", "if (!isIOS)"),
        (r"final url = '[^']*';", f"final url = '{SERVER}/download/android';"),
    )


if failed:
    print(f"\nERROR: {len(failed)} patch(es) failed, aborting build: {', '.join(failed)}")
    sys.exit(1)
print("\nAll patches applied.")
