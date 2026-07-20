/*
 * RDGen 中文 i18n 覆盖层（客户端运行时翻译）
 * ------------------------------------------------------------------
 * 由 rdgenerator/i18n_middleware.py 注入到每个 HTML 响应中。
 * 设计目标：0 侵入模板/表单/视图，方便从上游同步代码。
 *
 * 只需在此文件里维护「英文原文 -> 中文」词典即可：
 *   - DICT ：整段精确匹配（自动忽略首尾空白）
 *   - RULES：正则规则，用于带动态内容的文案（如 "Download xxx.exe"）
 *
 * 语言：默认中文；右上角按钮可切回英文（English 为源语言，切回即还原）。
 */
(function () {
  "use strict";

  var LANG_KEY = "rdgen_lang";
  var DEFAULT_LANG = "zh";

  function getLang() {
    try { return localStorage.getItem(LANG_KEY) || DEFAULT_LANG; }
    catch (e) { return DEFAULT_LANG; }
  }
  function setLang(v) {
    try { localStorage.setItem(LANG_KEY, v); } catch (e) {}
  }

  var lang = getLang();

  // 中文模式下先隐藏页面，翻译完成后再显示，避免英文闪一下（FOUC）。
  var hideStyle = null;
  if (lang === "zh") {
    try {
      hideStyle = document.createElement("style");
      hideStyle.id = "rdgen-i18n-hide";
      hideStyle.textContent = "html{visibility:hidden!important}";
      (document.head || document.documentElement).appendChild(hideStyle);
    } catch (e) {}
    // 安全兜底：无论如何 3 秒后一定显示，防止脚本异常导致白屏。
    setTimeout(reveal, 3000);
  }

  function reveal() {
    if (hideStyle && hideStyle.parentNode) {
      hideStyle.parentNode.removeChild(hideStyle);
    }
    hideStyle = null;
  }

  // ================= 词典（英文原文 -> 中文） =================
  var DICT = {
    // ---------- generator.html ----------
    "RustDesk Custom Client Builder": "RustDesk 定制客户端生成器",
    "Save/Load Configuration": "保存/加载配置",
    "Save Configuration": "保存配置",
    "Load Configuration": "加载配置",
    "Select Platform": "选择平台",
    "Windows 64Bit": "Windows 64 位",
    "Windows 32Bit": "Windows 32 位",
    "Rustdesk Version:": "Rustdesk 版本：",
    "'master' is the development version (nightly build) with the latest features but may be less stable":
      "“master” 是开发版（每夜构建），包含最新功能，但可能不够稳定",
    "nightly": "每夜构建版",
    "Fix connection delay when using third-party API": "修复使用第三方 API 时的连接延迟",

    "General": "常规",
    "Name of the configuration (no spaces or special characters, English characters only):":
      "配置名称（不能有空格或特殊字符，仅限英文字符）：",
    "Custom Application Name (leave blank to use default):": "自定义应用名称（留空则使用默认）：",
    "Connection Type:": "连接类型：",
    "Incoming Only": "仅被控（入站）",
    "Outgoing Only": "仅主控（出站）",
    "Bidirectional": "双向",
    "Disable Installation:": "禁用安装：",
    "No, enable installation": "否，启用安装",
    "Yes, DISABLE installation": "是，禁用安装",
    "Disable Settings:": "禁用设置：",
    "No, enable settings": "否，启用设置",
    "Yes, DISABLE settings": "是，禁用设置",
    "Custom Android App ID (replaces 'com.carriez.flutter_hbb', leave blank to use default):":
      "自定义 Android 应用 ID（替换 'com.carriez.flutter_hbb'，留空则使用默认）：",

    "Custom Server": "自定义服务器",
    "Host:": "主机（Host）：",
    "Key:": "密钥（Key）：",
    "Custom URL for links (replaces https://rustdesk.com):":
      "链接的自定义 URL（替换 https://rustdesk.com）：",
    "Custom URL for downloading updates (replaces https://rustdesk.com/download):":
      "下载更新的自定义 URL（替换 https://rustdesk.com/download）：",
    "Company name for copyright (replaces Purslane Tech Pte. Ltd.):":
      "版权公司名称（替换 Purslane Tech Pte. Ltd.）：",

    "Remote Config Center (optional)": "远程配置中心（可选）",
    "Point to your self-hosted rustdesk-config-server. When set, the client fetches host/key/api from this service on startup, and checks for updates through it (custom /version/latest direct download). Leave blank to disable.":
      "指向你自建的 rustdesk-config-server。填写后，客户端会在启动时从该服务拉取 host/key/api，并通过它检查更新（自定义 /version/latest 直连下载）。留空则不启用。",
    "Config Server URL (e.g. https://cfg.example.com):":
      "配置服务器 URL（例如 https://cfg.example.com）：",
    "Config Server Token (must match CLIENT_TOKEN):":
      "配置服务器 Token（必须与 CLIENT_TOKEN 一致）：",

    "Security": "安全",
    "Password Approve mode:": "密码授权模式：",
    "Accept sessions via password": "通过密码接受会话",
    "Accept sessions via click": "通过点击接受会话",
    "Accepts sessions via both": "以上两种方式均可",
    "To use the hide connection window feature, please set a permanent password.":
      "要使用隐藏连接窗口功能，请先设置永久密码。",
    "Set Permanent Password:": "设置永久密码：",
    "*The password is used as default, but can be changed by the client":
      "*该密码作为默认值，客户端仍可修改",
    "Deny LAN discovery": "禁止局域网发现",
    "Enable direct IP access": "启用直接 IP 访问",
    "Automatically close incoming sessions on user inactivity": "用户无操作时自动关闭入站会话",
    "Allow hiding the connection window from remote screen.": "允许在远程屏幕上隐藏连接窗口。",

    "Visual": "外观",
    "Custom App Icon (in .png format)": "自定义应用图标（.png 格式）",
    "Custom App Logo (in .png format)": "自定义应用 Logo（.png 格式）",
    "Custom Privacy Screen (in .png format)": "自定义隐私屏幕（.png 格式）",
    "Theme:": "主题：",
    "Light": "浅色",
    "Dark": "深色",
    "Follow System": "跟随系统",
    "Default": "默认",
    "Override": "强制覆盖",
    "*Default sets the theme but allows the client to change it, Override sets the theme permanently.":
      "*“默认”设置主题但允许客户端修改，“强制覆盖”则永久固定主题。",

    "Permissions": "权限",
    "The following Permissions can be set as default (the user can change the settings) or override (the settings cannot be changed).":
      "以下权限可设为“默认”（用户可修改）或“强制覆盖”（用户不可修改）。",
    "Permission type:": "权限类型：",
    "Custom": "自定义",
    "Full Access": "完全访问",
    "Screen share": "仅屏幕共享",
    "Enable keyboard/mouse": "启用键盘/鼠标",
    "Enable clipboard": "启用剪贴板",
    "Enable file transfer": "启用文件传输",
    "Enable audio": "启用音频",
    "Enable TCP tunneling": "启用 TCP 隧道",
    "Enable remote restart": "启用远程重启",
    "Enable recording session": "启用会话录制",
    "Enable blocking user input": "启用屏蔽用户输入",
    "Enable remote configuration modification": "启用远程修改配置",
    "Enable remote printer": "启用远程打印机",
    "Enable remote camera": "启用远程摄像头",
    "Enable remote terminal": "启用远程终端",

    "Code Changes": "代码改动",
    "Display an X for offline devices in the addressbook.": "在地址簿中为离线设备显示 X 标记。",
    "Remove notification for new versions.": "移除新版本更新提示。",

    "Other": "其他",
    "Remove wallpaper during incoming sessions": "入站会话期间移除壁纸",
    "Click here for a list of Default/Override settings": "点击此处查看 默认/覆盖 设置列表",
    "Default settings": "默认设置（default-settings）",
    "Override settings": "覆盖设置（override-settings）",
    "Generate Custom Client": "生成定制客户端",
    "Source Code on Github": "GitHub 源代码",
    "Donate": "赞助",

    // generator.html 里的 JS 提示
    "Filename is required.": "文件名不能为空。",
    "Error loading data. Invalid JSON file.": "加载数据出错：无效的 JSON 文件。",

    // ---------- waiting.html ----------
    "Generating Build": "正在生成构建",
    "Generating MacOS Build": "正在生成 macOS 构建",
    "Generating Windows Build": "正在生成 Windows 构建",
    "Generating Linux Build": "正在生成 Linux 构建",
    "Generating Android Build": "正在生成 Android 构建",
    "Build in Progress": "构建进行中",
    "This can take 30-45 minutes. You can leave this page open or come back later.":
      "这可能需要 30-45 分钟。你可以保持此页面打开，或稍后再回来查看。",
    "Status:": "状态：",
    "Technical View": "技术视图",
    "View GitHub Action Logs": "查看 GitHub Action 日志",
    "Note for macOS users: Generating an executable may require additional steps or permissions.":
      "macOS 用户请注意：生成可执行文件可能需要额外的步骤或权限。",
    "Initializing build process": "正在初始化构建流程",
    "Compiling source code": "正在编译源代码",
    "Generating platform-specific binaries": "正在生成平台专属二进制文件",
    "Packaging application": "正在打包应用",
    "Finalizing build": "正在完成构建",
    // 常见的 GitHub 构建状态（{{status}}）
    "queued": "排队中",
    "in_progress": "进行中",
    "completed": "已完成",
    "waiting": "等待中",
    "pending": "等待中",
    "success": "成功",
    "failure": "失败",

    // ---------- generated.html ----------
    "Build Generated Successfully": "构建生成成功",
    "MacOS Build Generated": "macOS 构建已生成",
    "Windows Build Generated": "Windows 构建已生成",
    "Linux Build Generated": "Linux 构建已生成",
    "Android Build Generated": "Android 构建已生成",
    "Error: No file generated": "错误：未生成任何文件",
    "Note: For macOS, you may need to adjust security settings to run the application.":
      "注意：在 macOS 上，你可能需要调整安全设置才能运行该应用。",
    "Note: You might need to disable SmartScreen or adjust Windows security settings.":
      "注意：你可能需要关闭 SmartScreen 或调整 Windows 安全设置。",
    "Note: Ensure you have the necessary dependencies installed.":
      "注意：请确保已安装所需的依赖项。",
    "Note: You may need to enable \"Unknown Sources\" in device settings.":
      "注意：你可能需要在设备设置中启用“未知来源”。",

    // ---------- failure.html ----------
    "Build Failure": "构建失败",
    "Windows Build Failed": "Windows 构建失败",
    "Workflow Interrupted": "工作流已中断",
    "Warning:": "警告：",
    "The build process did not complete successfully. Some files may be missing. You can attempt to download the available files below.":
      "构建过程未成功完成，部分文件可能缺失。你可以尝试下载下方可用的文件。",
    "Check GitHub Logs for error details ↗": "查看 GitHub 日志了解错误详情 ↗",
    "← Return to Form": "← 返回表单",

    // ---------- maintenance.html ----------
    "Rustdesk Client Generator": "Rustdesk 客户端生成器",
    "The Rustdesk Client Generator is currently under construction, please come back at a later time.":
      "Rustdesk 客户端生成器正在建设中，请稍后再来。"
  };

  // ================= 正则规则（用于带动态内容的文案） =================
  var RULES = [
    // 下载链接："Download myapp.exe" -> "下载 myapp.exe"
    [/^Download (?=\S)/, "下载 "]
  ];

  // 不翻译这些标签内部的文本（脚本/样式/用户输入等）
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, CODE: 1, PRE: 1 };

  // 标记：在我们自己写入 DOM 时，让 MutationObserver 跳过，避免自触发。
  var applying = false;

  function translateString(s) {
    if (!s) return s;
    var key = s.replace(/\s+/g, " ").trim();
    if (!key) return s;
    var hit = DICT[key];
    if (hit != null) {
      var lead = (s.match(/^\s*/) || [""])[0];
      var trail = (s.match(/\s*$/) || [""])[0];
      return lead + hit + trail;
    }
    for (var i = 0; i < RULES.length; i++) {
      if (RULES[i][0].test(s)) return s.replace(RULES[i][0], RULES[i][1]);
    }
    return s;
  }

  function translateTextNode(node) {
    var p = node.parentNode;
    if (p && SKIP_TAGS[p.nodeName]) return;
    var v = node.nodeValue;
    if (!v) return;
    var nv = translateString(v);
    if (nv !== v) node.nodeValue = nv;
  }

  function walk(root) {
    if (!root || !root.nodeType) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
    var nodes = [];
    var n;
    while ((n = walker.nextNode())) nodes.push(n);
    for (var i = 0; i < nodes.length; i++) translateTextNode(nodes[i]);
  }

  function translateAttrs(scope) {
    try {
      var root = (scope && scope.querySelectorAll) ? scope : document;
      var els = root.querySelectorAll("[placeholder],[title]");
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        var ph = el.getAttribute("placeholder");
        if (ph) { var t1 = translateString(ph); if (t1 !== ph) el.setAttribute("placeholder", t1); }
        var ti = el.getAttribute("title");
        if (ti) { var t2 = translateString(ti); if (t2 !== ti) el.setAttribute("title", t2); }
      }
    } catch (e) {}
  }

  function translateAll() {
    applying = true;
    try {
      walk(document.documentElement); // 含 <title>
      translateAttrs(document);
      var dt = translateString(document.title);
      if (dt !== document.title) document.title = dt;
    } finally {
      applying = false;
    }
  }

  function observe() {
    if (typeof MutationObserver === "undefined") return;
    var obs = new MutationObserver(function (muts) {
      if (applying) return;
      applying = true;
      try {
        for (var i = 0; i < muts.length; i++) {
          var m = muts[i];
          if (m.type === "characterData") {
            translateTextNode(m.target);
          } else if (m.type === "childList") {
            for (var j = 0; j < m.addedNodes.length; j++) {
              var an = m.addedNodes[j];
              if (an.nodeType === 3) translateTextNode(an);
              else if (an.nodeType === 1) { walk(an); translateAttrs(an); }
            }
          }
        }
      } finally {
        applying = false;
      }
    });
    obs.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true
    });
  }

  // 翻译 alert() 里的已知文案（不改模板，仅包一层）
  function hookAlert() {
    try {
      var raw = window.alert;
      window.alert = function (msg) {
        try { msg = translateString(String(msg)); } catch (e) {}
        return raw.call(window, msg);
      };
    } catch (e) {}
  }

  function addToggle() {
    if (!document.body) return;
    if (document.getElementById("rdgen-lang-toggle")) return;
    var btn = document.createElement("button");
    btn.id = "rdgen-lang-toggle";
    btn.type = "button";
    btn.setAttribute("data-i18n-skip", "1");
    btn.textContent = (lang === "zh") ? "EN" : "中文";
    btn.title = (lang === "zh") ? "Switch to English" : "切换为中文";
    btn.style.cssText =
      "position:fixed;top:12px;right:12px;z-index:2147483647;padding:6px 12px;" +
      "font-size:13px;line-height:1;border:1px solid rgba(127,127,127,.4);" +
      "border-radius:6px;background:rgba(0,0,0,.55);color:#fff;cursor:pointer;" +
      "font-family:system-ui,-apple-system,'Segoe UI',sans-serif;" +
      "box-shadow:0 2px 6px rgba(0,0,0,.25);";
    btn.addEventListener("click", function () {
      setLang(lang === "zh" ? "en" : "zh");
      location.reload();
    });
    document.body.appendChild(btn);
  }

  function run() {
    try {
      if (lang === "zh") {
        hookAlert();
        translateAll();
        observe();
      }
      addToggle();
    } catch (e) {
      // 忽略：出错也要保证下面 reveal 执行
    } finally {
      reveal();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
