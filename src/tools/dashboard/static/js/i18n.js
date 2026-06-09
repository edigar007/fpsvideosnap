(function () {
    const STORAGE_KEY = 'fpsvideosnap.language';

    const dictionaries = {
        en: {
            'language.label': 'Language',
            'language.en': 'English',
            'language.zh-CN': 'Chinese',
            'dashboard.title': 'FPS Video Snap - Dashboard',
            'dashboard.pro': 'PRO',
            'dashboard.ready': 'System ready',
            'dashboard.configSources': 'Config and sources',
            'dashboard.targetGame': 'Target game',
            'dashboard.loading': 'Loading...',
            'dashboard.videoDirectory': 'Video directory',
            'dashboard.directoryPlaceholder': 'Example: D:\\Videos\\Battlefield 2042',
            'dashboard.scan': 'Scan',
            'dashboard.selectAll': 'Select all',
            'dashboard.fileCount': '{count} file(s)',
            'dashboard.emptyScan': 'Scan a directory to find video files',
            'dashboard.selected': 'Selected',
            'dashboard.start': 'Start clipping',
            'dashboard.progress': 'Processing progress',
            'dashboard.waiting': 'Waiting to start...',
            'dashboard.metadata': 'Video metadata',
            'dashboard.frames': 'Frame extraction',
            'dashboard.detection': 'Kill detection',
            'dashboard.clips': 'Clip extraction',
            'dashboard.join': 'Video joining',
            'dashboard.audio': 'Audio mixing',
            'dashboard.detectedKills': 'Detected kills',
            'dashboard.extractedClips': 'Extracted clips',
            'dashboard.outputFiles': 'Generated files',
            'dashboard.errorLog': 'Error log',
            'dashboard.status': 'Status:',
            'dashboard.idle': 'Idle',
            'dashboard.cancel': 'Cancel task',
            'dashboard.noGames': 'No game configs found',
            'dashboard.loadGamesFailed': 'Unable to load game list',
            'dashboard.directoryRequired': 'Enter a video directory.',
            'dashboard.scanning': 'Scanning...',
            'dashboard.scanFailed': 'Directory scan failed',
            'dashboard.noVideos': 'No video files found (.mp4, .mkv, .avi)',
            'dashboard.taskStarted': 'Task started.',
            'dashboard.startFailed': 'Start failed: {error}',
            'dashboard.startRequestFailed': 'Start request failed',
            'dashboard.cancelConfirm': 'Cancel the current task?',
            'dashboard.taskCancelled': 'Task cancelled.',
            'dashboard.cancelFailed': 'Cancel request failed',
            'dashboard.preparing': 'Preparing...',
            'dashboard.running': 'Processing...',
            'dashboard.completed': 'Completed',
            'dashboard.failed': 'Failed',
            'dashboard.cancelled': 'Cancelled',
            'dashboard.busy': 'System busy',
            'dashboard.copyPath': 'Copy path',
            'dashboard.pathCopied': 'Generated file path copied.',
            'dashboard.generatedFile': 'Generated file'
        },
        'zh-CN': {
            'language.label': '语言',
            'language.en': '英文',
            'language.zh-CN': '中文',
            'dashboard.title': 'FPS Video Snap - 剪辑控制台',
            'dashboard.pro': 'PRO',
            'dashboard.ready': '系统就绪',
            'dashboard.configSources': '配置与源文件',
            'dashboard.targetGame': '目标游戏',
            'dashboard.loading': '加载中...',
            'dashboard.videoDirectory': '视频目录',
            'dashboard.directoryPlaceholder': '例如: D:\\Videos\\Battlefield 2042',
            'dashboard.scan': '扫描',
            'dashboard.selectAll': '全选',
            'dashboard.fileCount': '{count} 个文件',
            'dashboard.emptyScan': '请扫描目录以查找视频文件',
            'dashboard.selected': '已选',
            'dashboard.start': '开始剪辑',
            'dashboard.progress': '处理进度',
            'dashboard.waiting': '等待开始...',
            'dashboard.metadata': '视频元数据',
            'dashboard.frames': '帧提取',
            'dashboard.detection': '击杀检测',
            'dashboard.clips': '片段提取',
            'dashboard.join': '视频拼接',
            'dashboard.audio': '音频混合',
            'dashboard.detectedKills': '检测到的击杀',
            'dashboard.extractedClips': '提取的片段',
            'dashboard.outputFiles': '生成文件位置',
            'dashboard.errorLog': '错误日志',
            'dashboard.status': '状态:',
            'dashboard.idle': '空闲',
            'dashboard.cancel': '取消任务',
            'dashboard.noGames': '未找到游戏配置',
            'dashboard.loadGamesFailed': '无法加载游戏列表',
            'dashboard.directoryRequired': '请输入视频目录。',
            'dashboard.scanning': '扫描中...',
            'dashboard.scanFailed': '扫描目录失败',
            'dashboard.noVideos': '未找到视频文件 (.mp4, .mkv, .avi)',
            'dashboard.taskStarted': '任务已启动。',
            'dashboard.startFailed': '启动失败: {error}',
            'dashboard.startRequestFailed': '启动请求失败',
            'dashboard.cancelConfirm': '确定要取消当前任务吗？',
            'dashboard.taskCancelled': '任务已取消。',
            'dashboard.cancelFailed': '取消请求失败',
            'dashboard.preparing': '准备中...',
            'dashboard.running': '处理中...',
            'dashboard.completed': '已完成',
            'dashboard.failed': '失败',
            'dashboard.cancelled': '已取消',
            'dashboard.busy': '系统忙碌',
            'dashboard.copyPath': '复制路径',
            'dashboard.pathCopied': '已复制生成文件路径。',
            'dashboard.generatedFile': '生成文件'
        }
    };

    function interpolate(template, params) {
        return String(template).replace(/\{(\w+)\}/g, (_, key) => {
            return Object.prototype.hasOwnProperty.call(params, key) ? params[key] : `{${key}}`;
        });
    }

    function getLanguage() {
        const saved = localStorage.getItem(STORAGE_KEY);
        return dictionaries[saved] ? saved : 'en';
    }

    function t(key, params = {}) {
        const lang = getLanguage();
        const template = dictionaries[lang]?.[key] || dictionaries.en[key] || key;
        return interpolate(template, params);
    }

    function translatePage() {
        document.documentElement.lang = getLanguage();
        document.querySelectorAll('[data-i18n]').forEach((el) => {
            el.textContent = t(el.dataset.i18n);
        });
        document.querySelectorAll('[data-i18n-title]').forEach((el) => {
            el.title = t(el.dataset.i18nTitle);
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
            el.placeholder = t(el.dataset.i18nPlaceholder);
        });
        document.querySelectorAll('[data-i18n-language-select]').forEach((select) => {
            const current = getLanguage();
            select.innerHTML = Object.keys(dictionaries).map((lang) => {
                const selected = lang === current ? ' selected' : '';
                return `<option value="${lang}"${selected}>${t(`language.${lang}`)}</option>`;
            }).join('');
        });
        document.title = t(document.body.dataset.i18nTitle || 'dashboard.title');
    }

    function setLanguage(lang) {
        if (!dictionaries[lang]) return;
        localStorage.setItem(STORAGE_KEY, lang);
        translatePage();
        document.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
    }

    window.i18n = { languages: dictionaries, t, setLanguage, getLanguage, translatePage };

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-i18n-language-select]').forEach((select) => {
            select.addEventListener('change', (event) => setLanguage(event.target.value));
        });
        translatePage();
    });
}());
