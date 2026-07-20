#!/usr/bin/env python3
"""
rdpatch.py — 给 RustDesk 客户端源码打入「远程配置中心 + 自定义更新服务器」补丁。

在 rdgen 的 GitHub Actions 里,checkout 好 rustdesk 源码后运行本脚本。
它通过正则做定点替换(对 1.4.x 各版本较稳健),完成:

  P1  版本检查 URL      -> 指向自建服务器 /version/latest        (hbb_common/src/lib.rs)
  P2  版本检查带 token   -> Authorization: Bearer <token>          (src/common.rs)
  P3  解析 version 字段  -> 用 serde_json::Value 读 url + version   (src/common.rs)
  P4  直连下载          -> 直接用服务器返回的下载链接,不再拼 GitHub  (src/updater.rs)
  P5  启动拉取配置       -> 注入 fetch_remote_config()             (src/common.rs)
  P6  放开 custom 限制   -> 定制客户端也检查/提示更新                (common.rs + flutter)

配置来自环境变量:
  RD_CONFIG_SERVER   自建服务器地址,例如 https://cfg.example.com  (必填)
  RD_CONFIG_TOKEN    客户端接口 Bearer token                        (必填)

用法:
  RD_CONFIG_SERVER=https://cfg.example.com RD_CONFIG_TOKEN=xxx python rdpatch.py [rustdesk_root]
"""
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SERVER = os.environ.get("RD_CONFIG_SERVER", "").rstrip("/")
TOKEN = os.environ.get("RD_CONFIG_TOKEN", "")

results = []  # (name, ok, critical)


def _p(root, *parts):
    return os.path.join(root, *parts)


def patch_file(rel, name, transform, critical=False):
    """读取文件 -> transform(text)->(new_text, changed) -> 写回。"""
    path = _p(ROOT, *rel.split("/"))
    if not os.path.isfile(path):
        print(f"[MISS] {name}: file not found -> {path}")
        results.append((name, False, critical))
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    try:
        new_text, changed = transform(text)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name}: {e}")
        results.append((name, False, critical))
        return
    if not changed:
        print(f"[SKIP] {name}: pattern not found (maybe already patched) -> {rel}")
        results.append((name, False, critical))
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"[ OK ] {name} -> {rel}")
    results.append((name, True, critical))


def sub_once(pattern, repl, text, flags=0):
    new_text, n = re.subn(pattern, repl, text, count=1, flags=flags)
    return new_text, n > 0


# --------------------------------------------------------------------------
# P1: 版本检查 URL(hbb_common,submodule 已 recursive checkout)
# --------------------------------------------------------------------------
def p1(text):
    return sub_once(
        r'const URL: &str = "https://api\.rustdesk\.com/version/latest";',
        f'const URL: &str = "{SERVER}/version/latest";',
        text,
    )


patch_file("libs/hbb_common/src/lib.rs", "P1 version-check URL", p1, critical=True)


# --------------------------------------------------------------------------
# src/common.rs: P2 + P3 + P5 + P6(部分)+ 注入常量与函数
# --------------------------------------------------------------------------
def common_rs(text):
    changed_any = False

    # P2: 给两处 version 检查请求加 Authorization 头
    text2, c = re.subn(
        r'\.post\(&url\)\.json\(&request\)',
        '.post(&url).header("Authorization", format!("Bearer {}", REMOTE_CONFIG_TOKEN)).json(&request)',
        text,
    )
    if c:
        text = text2
        changed_any = True
        print(f"       P2 auth header applied to {c} request(s)")

    # P3: 用 serde_json::Value 解析 url + version
    text, c = sub_once(
        r'let resp: hbb_common::VersionCheckResponse = serde_json::from_slice\(&bytes\)\?;\s*\n'
        r'\s*let response_url = resp\.url;\s*\n'
        r"\s*let latest_release_version = response_url\.rsplit\('/'\)\.next\(\)\.unwrap_or_default\(\);",
        "let resp: serde_json::Value = serde_json::from_slice(&bytes)?;\n"
        '    let response_url = resp.get("url").and_then(|v| v.as_str()).unwrap_or_default().to_string();\n'
        '    let latest_release_version = resp.get("version").and_then(|v| v.as_str()).unwrap_or_default().to_string();',
        text,
    )
    changed_any = changed_any or c

    # P5: global_init 里注入配置拉取
    text, c = sub_once(
        r'pub fn global_init\(\) -> bool \{\n',
        "pub fn global_init() -> bool {\n    fetch_remote_config();\n",
        text,
    )
    changed_any = changed_any or c

    # P6a: check_software_update 去掉 custom client 提前 return
    text, c = sub_once(
        r'pub fn check_software_update\(\) \{\n\s*if is_custom_client\(\) \{\n\s*return;\n\s*\}\n',
        "pub fn check_software_update() {\n",
        text,
    )
    changed_any = changed_any or c

    # P7a: key 隐藏层 —— get_key 在 option("key") 为空时读下发的 key(不写 option,故界面不显示)
    text, c = sub_once(
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
        text,
    )
    changed_any = changed_any or c

    # P7b: api 隐藏层 —— get_api_server_ 在 api(option) 为空时读下发的 api(不写 option,故不显示)
    text, c = sub_once(
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
        text,
    )
    changed_any = changed_any or c

    # 注入常量 + fetch_remote_config()(追加到文件末尾)
    if "REMOTE_CONFIG_SERVER" not in text:
        text += f'''

// ==== injected by rdpatch.py: remote config center ====
pub const REMOTE_CONFIG_SERVER: &str = "{SERVER}";
pub const REMOTE_CONFIG_TOKEN: &str = "{TOKEN}";

lazy_static::lazy_static! {{
    // 隐藏层:不写入 option,故客户端设置界面不显示 host/key/api(与上游 sed 常量效果一致)。
    // host 走 hbb_common 的 PROD_RENDEZVOUS_SERVER;key/api 走下面两个全局量,
    // 由 patch 后的 get_key / get_api_server_ 在 option 为空时读取。
    static ref REMOTE_CFG_KEY: std::sync::RwLock<String> = Default::default();
    static ref REMOTE_CFG_API: std::sync::RwLock<String> = Default::default();
}}

/// 启动时从自建服务器拉取 host/key/api 写入“隐藏层”(不写 option,界面不显示)。
/// 同步执行(独立线程 + join,避免与 tokio 运行时冲突),确保连接/注册前配置已就绪;
/// 用 Once 保证进程内只拉取一次。拉取失败则回落到编译期默认(rdgen sed 的常量)。
pub fn fetch_remote_config() {{
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| {{
        let _ = std::thread::spawn(|| {{
            do_fetch_remote_config();
        }})
        .join();
    }});
}}

fn do_fetch_remote_config() {{
    let url = format!("{{}}/config", REMOTE_CONFIG_SERVER);
    let client = match reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(6))
        .build()
    {{
        Ok(c) => c,
        Err(e) => {{
            log::error!("fetch_remote_config build client: {{e}}");
            return;
        }}
    }};
    let resp = match client
        .get(&url)
        .header("Authorization", format!("Bearer {{}}", REMOTE_CONFIG_TOKEN))
        .send()
    {{
        Ok(r) => r,
        Err(e) => {{
            log::error!("fetch_remote_config request: {{e}}");
            return;
        }}
    }};
    let value: serde_json::Value = match resp.json() {{
        Ok(v) => v,
        Err(e) => {{
            log::error!("fetch_remote_config parse: {{e}}");
            return;
        }}
    }};
    if let Some(s) = value.get("host").and_then(|v| v.as_str()) {{
        if !s.is_empty() {{
            *hbb_common::config::PROD_RENDEZVOUS_SERVER.write().unwrap() = s.to_owned();
        }}
    }}
    if let Some(s) = value.get("key").and_then(|v| v.as_str()) {{
        if !s.is_empty() {{
            *REMOTE_CFG_KEY.write().unwrap() = s.to_owned();
        }}
    }}
    if let Some(s) = value.get("api").and_then(|v| v.as_str()) {{
        if !s.is_empty() {{
            *REMOTE_CFG_API.write().unwrap() = s.to_owned();
        }}
    }}
    log::info!("remote config applied (hidden) from {{}}", REMOTE_CONFIG_SERVER);
}}
'''
        changed_any = True

    return text, changed_any


patch_file("src/common.rs", "P2/P3/P5/P6 common.rs", common_rs, critical=True)


# --------------------------------------------------------------------------
# P4: src/updater.rs 直连下载(去掉 tag->download 与文件名拼接)
# --------------------------------------------------------------------------
def updater_rs(text):
    return sub_once(
        r'let download_url = update_url\.replace\("tag", "download"\);.*?'
        r'-x86-sciter\.exe", download_url, version\)\s*\};',
        "let download_url = update_url.clone();\n"
        "        let version = download_url.split('/').last().unwrap_or_default();",
        text,
        flags=re.DOTALL,
    )


patch_file("src/updater.rs", "P4 direct download (updater.rs)", updater_rs, critical=True)


# --------------------------------------------------------------------------
# P4b: Flutter 桌面下载直接用返回链接
# --------------------------------------------------------------------------
def update_progress_dart(text):
    return sub_once(
        r"String downloadUrl = releasePageUrl\.replaceAll\('tag', 'download'\);.*?"
        r"downloadUrl = '\$downloadUrl/\$downloadFile';",
        "String downloadUrl = releasePageUrl;",
        text,
        flags=re.DOTALL,
    )


patch_file(
    "flutter/lib/desktop/widgets/update_progress.dart",
    "P4b direct download (flutter)",
    update_progress_dart,
)


# --------------------------------------------------------------------------
# P6b: Flutter 放开 custom client 更新提示
# --------------------------------------------------------------------------
def common_dart(text):
    return sub_once(
        r'if \(!isWeb\) \{\n\s*if \(!bind\.isCustomClient\(\)\) \{',
        "if (!isWeb) {\n    if (true) {",
        text,
    )


patch_file("flutter/lib/common.dart", "P6b checkUpdate guard (flutter)", common_dart)


def desktop_home_dart(text):
    return sub_once(
        r'if \(!bind\.isCustomClient\(\) &&\s*\n'
        r'\s*updateUrl\.isNotEmpty &&\s*\n'
        r'\s*!isCardClosed &&\s*\n'
        r"\s*bind\.mainUriPrefixSync\(\)\.contains\('rustdesk'\)\) \{",
        "if (updateUrl.isNotEmpty &&\n        !isCardClosed) {",
        text,
    )


patch_file(
    "flutter/lib/desktop/pages/desktop_home_page.dart",
    "P6c update card guard (flutter)",
    desktop_home_dart,
)


def connection_page_dart(text):
    return sub_once(
        r'if \(!bind\.isCustomClient\(\) && !isIOS\)',
        "if (!isIOS)",
        text,
    )


patch_file(
    "flutter/lib/mobile/pages/connection_page.dart",
    "P6d mobile update card guard (flutter)",
    connection_page_dart,
)


# --------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------
print("\n===== rdpatch summary =====")
crit_fail = False
for name, ok, critical in results:
    tag = "OK " if ok else ("CRIT-FAIL" if critical else "warn")
    print(f"  [{tag}] {name}")
    if critical and not ok:
        crit_fail = True

if not SERVER or not TOKEN:
    print("\nERROR: RD_CONFIG_SERVER / RD_CONFIG_TOKEN must be set")
    sys.exit(2)

if crit_fail:
    print("\nERROR: one or more CRITICAL patches failed; aborting build")
    sys.exit(1)

print("\nAll critical patches applied.")
