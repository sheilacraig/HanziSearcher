// 常用与难打偏旁部首集合 (带拼音与字义注释)
    const FREQUENT_RADICALS = [
      { c: "氵", s: "水", t: "三点水 (水部)" },
      { c: "亻", s: "人", t: "单人旁 (人部)" },
      { c: "扌", s: "手", t: "提手旁 (手部)" },
      { c: "艹", s: "草", t: "草字头 (艸部)" },
      { c: "辶", s: "走", t: "走之底 (辵部)" },
      { c: "阝", s: "耳", t: "双耳旁 (阜/邑部)" },
      { c: "犭", s: "犬", t: "反犬旁 (犬部)" },
      { c: "饣", s: "食", t: "食字旁 (食部)" },
      { c: "纟", s: "丝", t: "绞丝旁 (糸部)" },
      { c: "宀", s: "宝", t: "宝盖头" },
      { c: "礻", s: "示", t: "示字旁 (示部)" },
      { c: "衤", s: "衣", t: "衣字旁 (衣部)" },
      { c: "攵", s: "文", t: "反文旁 (攴部)" },
      { c: "灬", s: "火", t: "四点底 (火部)" },
      { c: "冫", s: "冰", t: "两点水" },
      { c: "冖", s: "秃", t: "秃宝盖" },
      { c: "冂", s: "同", t: "同字框" },
      { c: "匚", s: "框", t: "三框栏" },
      { c: "凵", s: "凶", t: "下框" },
      { c: "刂", s: "刀", t: "立刀旁 (刀部)" },
      { c: "勹", s: "包", t: "包字头" },
      { c: "匕", s: "匕", t: "匕部" },
      { c: "卜", s: "卜", t: "卜部" },
      { c: "卩", s: "印", t: "单耳刀 (卩部)" },
      { c: "厶", s: "私", t: "私字旁" },
      { c: "廴", s: "建", t: "建字底" },
      { c: "弋", s: "弋", t: "弋部" },
      { c: "弓", s: "弓", t: "弓字旁" },
      { c: "彡", s: "撇", t: "三撇旁" },
      { c: "彳", s: "行", t: "双人旁 (彳部)" },
      { c: "疒", s: "病", t: "病字旁" },
      { c: "癶", s: "登", t: "登字头" },
      { c: "虍", s: "虎", t: "虎字头" },
      { c: "疋", s: "疋", t: "疋部" },
      { c: "⺮", s: "竹", t: "竹字头" },
      { c: "⺶", s: "羊", t: "羊字头" },
      { c: "⻊", s: "足", t: "足字旁" },
      { c: "⻢", s: "马", t: "马字旁" },
      { c: "⻥", s: "鱼", t: "鱼字旁" },
      { c: "⻦", s: "鸟", t: "鸟字旁" },
      { c: "豸", s: "豹", t: "豸部" },
      { c: "隹", s: "雀", t: "隹部" },
      { c: "髟", s: "发", t: "髟部" },
      { c: "鬯", s: "酒", t: "鬯部" },
      { c: "鬲", s: "鼎", t: "鬲部" }
    ];

    // 214 康熙部首全集 (按 1~17 笔画排序)
    const KANGXI_RADICALS = {
      1: ["一", "丨", "丿", "丶", "乙", "亅"],
      2: ["二", "亠", "人", "儿", "入", "八", "冂", "冖", "冫", "几", "凵", "刀", "力", "勹", "匕", "匚", "匸", "十", "卜", "卩", "厂", "厶", "又"],
      3: ["口", "囗", "土", "士", "夂", "夕", "大", "女", "子", "宀", "寸", "小", "尢", "尸", "屮", "山", "巛", "工", "己", "巾", "干", "幺", "广", "廴", "廾", "弋", "弓", "彐", "彡", "彳"],
      4: ["心", "戈", "戶", "手", "支", "攴", "文", "斗", "斤", "方", "无", "日", "曰", "月", "木", "欠", "止", "歹", "殳", "毋", "比", "毛", "氏", "气", "水", "火", "爪", "父", "爻", "爿", "片", "牙", "牛", "犬"],
      5: ["玄", "玉", "瓜", "瓦", "甘", "生", "用", "田", "疋", "疒", "癶", "白", "皮", "皿", "目", "矛", "矢", "石", "示", "禸", "禾", "穴", "立"],
      6: ["竹", "米", "糸", "缶", "网", "羊", "羽", "老", "而", "耒", "耳", "聿", "肉", "臣", "自", "至", "臼", "舌", "舛", "舟", "艮", "色", "艸", "虍", "虫", "血", "行", "衣", "襾"],
      7: ["見", "角", "言", "谷", "豆", "豕", "豸", "貝", "赤", "走", "足", "身", "車", "辛", "辰", "辵", "邑", "酉", "釆", "里"],
      8: ["金", "長", "門", "阜", "隶", "隹", "雨", "靑", "非"],
      9: ["面", "革", "韋", "韭", "音", "頁", "風", "飛", "食", "首", "香"],
      10: ["馬", "骨", "高", "髟", "鬥", "鬯", "鬲", "鬼"],
      11: ["魚", "鳥", "鹵", "鹿", "麥", "麻"],
      12: ["黃", "黍", "黑", "黹"],
      13: ["黽", "鼎", "鼓", "鼠"],
      14: ["鼻", "齊"],
      15: ["齒"],
      16: ["龍", "龜"],
      17: ["龠"]
    };

    const searchInput = document.getElementById('searchInput');
    const strokesInput = document.getElementById('strokesInput');
    const searchBtn = document.getElementById('searchBtn');
    const resetBtn = document.getElementById('resetBtn');
    const clearSearchIcon = document.getElementById('clearSearchIcon');
    const clearStrokesIcon = document.getElementById('clearStrokesIcon');

    const resultsGrid = document.getElementById('resultsGrid');
    const statusText = document.getElementById('statusText');
    const countText = document.getElementById('countText');
    const toast = document.getElementById('copyToast');

    const paginationBar = document.getElementById('paginationBar');
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');
    const pageInfoText = document.getElementById('pageInfoText');
    const jumpPageInput = document.getElementById('jumpPageInput');

    const fontStudioPanel = document.getElementById('fontStudioPanel');
    const fontStatusDot = document.getElementById('fontStatusDot');
    const fontStatusTitle = document.getElementById('fontStatusTitle');
    const fontStatusDesc = document.getElementById('fontStatusDesc');
    const resetFontBtn = document.getElementById('resetFontBtn');
    const fontFileInput = document.getElementById('fontFileInput');

    // 模态弹窗元素
    const familyModal = document.getElementById('familyModal');
    const modalGlyph = document.getElementById('modalGlyph');
    const modalTitle = document.getElementById('modalTitle');
    const modalMeta = document.getElementById('modalMeta');
    const modalParents = document.getElementById('modalParents');
    const modalVariants = document.getElementById('modalVariants');
    const modalDescendants = document.getElementById('modalDescendants');

    // 视觉设置状态
    let showMizige = true;
    let currentGridSize = 'normal';

    // 全局字体状态 (优先使用字体，没有的字形使用 svg，默认未上传使用 svg)
    let customFontActive = false;
    let customFontName = '';
    let customFontGlyphs = new Set();

    let currentResults = [];
    let debounceTimer = null;

    let currentPage = 1;
    let totalPages = 1;
    let totalCount = 0;
    const pageSize = 50;

    let savedCursorStart = searchInput.value.length;
    let savedCursorEnd = searchInput.value.length;

    function recordCursor() {
      if (typeof searchInput.selectionStart === 'number') {
        savedCursorStart = searchInput.selectionStart;
        savedCursorEnd = searchInput.selectionEnd;
      }
    }

    searchInput.addEventListener('keyup', recordCursor);
    searchInput.addEventListener('mouseup', recordCursor);
    searchInput.addEventListener('select', recordCursor);
    searchInput.addEventListener('input', () => {
      recordCursor();
      updateClearIcons();
    });

    strokesInput.addEventListener('input', updateClearIcons);

    function updateClearIcons() {
      clearSearchIcon.style.display = searchInput.value ? 'block' : 'none';
      clearStrokesIcon.style.display = strokesInput.value ? 'block' : 'none';
    }

    function clearInput(id) {
      const el = document.getElementById(id);
      el.value = '';
      updateClearIcons();
      el.focus();
      triggerAutoSearch();
    }

    // HTML 转义：所有动态文本写入 innerHTML 前必须经过此函数（XSS 防护，审查报告 P0-3）
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // 统一 fetch 封装：检查 HTTP 状态码，服务端 4xx/5xx 不再被伪装成"无结果"
    async function fetchJson(url, opts) {
      const res = await fetch(url, opts);
      if (!res.ok) {
        let detail = '';
        try { const j = await res.json(); detail = j.error || ''; } catch (e) {}
        throw new Error(`HTTP ${res.status}${detail ? '：' + detail : ''}`);
      }
      return res.json();
    }

    let toastTimer = null;
    function showToast(msg) {
      toast.innerText = msg;
      toast.style.display = 'block';
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => { toast.style.display = 'none'; }, 1600);
    }

    // 视图设置：米字格切换
    function toggleMizige(enable) {
      showMizige = enable;
      document.querySelectorAll('.glyph-display').forEach(el => {
        if (enable) el.classList.add('with-mizige');
        else el.classList.remove('with-mizige');
      });
      if (modalGlyph) {
        if (enable) modalGlyph.classList.add('with-mizige');
        else modalGlyph.classList.remove('with-mizige');
      }
    }

    // 视图设置：字形尺寸切换
    function setGridSize(size, btnEl) {
      currentGridSize = size;
      document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('active'));
      if (btnEl) btnEl.classList.add('active');

      resultsGrid.classList.remove('grid-size-compact', 'grid-size-large');
      if (size === 'compact') resultsGrid.classList.add('grid-size-compact');
      if (size === 'large') resultsGrid.classList.add('grid-size-large');
    }

    // 快捷场景预设 (Quick Presets)
    function applyPreset(query, strokes) {
      searchInput.value = query;
      strokesInput.value = strokes;
      updateClearIcons();
      currentPage = 1;
      doSearch(1);
    }

    // 偏旁部首与构字符号辅助工具箱折叠/展开切换
    function toggleToolbox() {
      const container = document.getElementById('toolboxContainer');
      const indicator = document.getElementById('toolboxToggleIndicator');
      if (container.style.display === 'none' || !container.style.display) {
        container.style.display = 'block';
        indicator.innerHTML = '收起 ▲';
      } else {
        container.style.display = 'none';
        indicator.innerHTML = '展开 ▼';
      }
    }

    // 工具箱 Tab 切换
    function switchToolboxTab(tabId, btnEl) {
      document.querySelectorAll('.toolbox-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.toolbox-content-panel').forEach(p => p.classList.remove('active'));
      btnEl.classList.add('active');
      document.getElementById(tabId).classList.add('active');
    }

    // 214 康熙部首快速笔画过滤
    function filterKangxi(strokeNum, btnEl) {
      document.querySelectorAll('.stroke-nav-pill').forEach(b => b.classList.remove('active'));
      btnEl.classList.add('active');

      const groups = document.querySelectorAll('.kangxi-row-group');
      groups.forEach(g => {
        const s = parseInt(g.getAttribute('data-stroke'), 10);
        if (strokeNum === 0 || s === strokeNum) {
          g.classList.remove('hidden');
        } else {
          g.classList.add('hidden');
        }
      });
    }

    // 初始化工具箱数据与 DOM
    function initToolbox() {
      // 1. 常用难打部首
      const freqContainer = document.getElementById('frequentRadicalsContainer');
      freqContainer.innerHTML = FREQUENT_RADICALS.map(item => `
        <button class="rad-tag-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('${item.c}')" title="${item.c}: ${item.t}">
          <span>${item.c}</span>
          <span class="rad-sub">${item.s}</span>
        </button>
      `).join('');

      // 2. 214 康熙部首检字表与笔画快捷导航
      const filterBar = document.getElementById('kangxiFilterBar');
      const kxContainer = document.getElementById('kangxiListContainer');
      let kxHtml = '';

      for (let s = 1; s <= 17; s++) {
        const rads = KANGXI_RADICALS[s];
        if (!rads || rads.length === 0) continue;

        // 导航胶囊
        const pill = document.createElement('button');
        pill.className = 'stroke-nav-pill';
        pill.innerText = `${s}画 (${rads.length})`;
        pill.onclick = function() { filterKangxi(s, this); };
        filterBar.appendChild(pill);

        // 内容组
        kxHtml += `
          <div class="kangxi-row-group" data-stroke="${s}">
            <span class="kangxi-group-title">${s} 画:</span>
            <div style="display:flex; flex-wrap:wrap; gap:5px;">
              ${rads.map(r => `
                <button class="rad-tag-btn" onmousedown="event.preventDefault();" onclick="insertSymbol('${r}')" title="${r} (康熙部首 ${s}画)">
                  ${r}
                </button>
              `).join('')}
            </div>
          </div>
        `;
      }
      kxContainer.innerHTML = kxHtml;
    }

    // 在光标处插入符号或部首
    function insertSymbol(sym) {
      searchInput.focus();

      let startPos = (typeof searchInput.selectionStart === 'number') ? searchInput.selectionStart : savedCursorStart;
      let endPos = (typeof searchInput.selectionEnd === 'number') ? searchInput.selectionEnd : savedCursorEnd;

      const text = searchInput.value;
      searchInput.value = text.substring(0, startPos) + sym + text.substring(endPos);

      const nextPos = startPos + sym.length;
      searchInput.setSelectionRange(nextPos, nextPos);
      savedCursorStart = savedCursorEnd = nextPos;

      updateClearIcons();
      currentPage = 1;
      triggerAutoSearch();
    }

    // 点击部件穿透搜索
    function drillComponent(comp) {
      searchInput.value = comp;
      updateClearIcons();
      currentPage = 1;
      doSearch(1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // 字体管理与加载系统
    async function initFontSystem() {
      try {
        const data = await fetchJson('/api/current_font');
        if (data.has_font) {
          await applyFont(data);
        } else {
          setNoFontState();
        }
      } catch (e) {
        setNoFontState();
      }
    }

    async function applyFont(meta) {
      try {
        const fontFace = new FontFace('UserCustomFont', `url(/api/font_file?t=${Date.now()})`);
        await fontFace.load();
        document.fonts.add(fontFace);

        customFontActive = true;
        customFontName = meta.font_name || '自定义字体';
        customFontGlyphs = new Set(meta.codepoints || []);

        fontStatusDot.className = 'font-pulse-dot active';
        fontStatusTitle.innerHTML = `<span>🟢 自定义字体已就绪: <b>${esc(customFontName)}</b></span>`;
        fontStatusDesc.innerHTML = `已精准加载 <b>${customFontGlyphs.size}</b> 个字形。覆盖汉字优先字体呈现，缺失字形自动降级使用 SVG。`;
        resetFontBtn.style.display = 'inline-flex';

        if (currentResults.length > 0) {
          renderCards(currentResults);
        }
      } catch (err) {
        showToast('自定义字体加载失败: ' + err.message);
        setNoFontState();
      }
    }

    function setNoFontState() {
      customFontActive = false;
      customFontName = '';
      customFontGlyphs = new Set();

      fontStatusDot.className = 'font-pulse-dot';
      fontStatusTitle.innerHTML = '<span>当前字形源: 默认 SVG 矢量直出</span>';
      fontStatusDesc.innerText = '未加载自定义字体，所有汉字均采用矢量 SVG 呈现。支持拖拽 TTF / OTF 到此处一键加载。';
      resetFontBtn.style.display = 'none';

      if (currentResults.length > 0) {
        renderCards(currentResults);
      }
    }

    // 上传文件处理 (普通选择或拖拽上传)
    async function handleUploadFontFile(file) {
      if (!file) return;
      fontStatusDesc.innerText = `正在解析并载入字体: ${file.name}...`;

      try {
        const data = await fetchJson(`/api/upload_font?filename=${encodeURIComponent(file.name)}`, {
          method: 'POST',
          body: file
        });
        if (data.success) {
          await applyFont(data);
          showToast(`成功加载字体: ${data.font_name} (包含 ${data.glyph_count} 个字形)`);
        } else {
          showToast('上传失败: ' + (data.error || '未知错误'));
          setNoFontState();
        }
      } catch (err) {
        showToast('上传出错: ' + err.message);
        setNoFontState();
      }
      fontFileInput.value = '';
    }

    fontFileInput.addEventListener('change', (e) => {
      handleUploadFontFile(e.target.files[0]);
    });

    // 拖拽字体到面板直接上传
    fontStudioPanel.addEventListener('dragover', (e) => {
      e.preventDefault();
      fontStudioPanel.classList.add('drag-over');
    });
    fontStudioPanel.addEventListener('dragleave', () => {
      fontStudioPanel.classList.remove('drag-over');
    });
    fontStudioPanel.addEventListener('drop', (e) => {
      e.preventDefault();
      fontStudioPanel.classList.remove('drag-over');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleUploadFontFile(e.dataTransfer.files[0]);
      }
    });


    // 恢复默认 SVG 渲染
    async function resetToDefaultSvg() {
      try {
        await fetchJson('/api/reset_font', { method: 'POST' });
        setNoFontState();
        showToast('已恢复为默认 SVG 矢量直出模式');
      } catch (err) {
        showToast('重置失败：' + err.message);
        setNoFontState();
      }
    }

    // 辅助：构建字形来源微徽章 (置于米字格外部，绝对不遮挡汉字)
    function buildSourceBadge(char) {
      const cp = char ? char.codePointAt(0) : 0;
      const hasGlyph = customFontActive && customFontGlyphs.has(cp);
      if (hasGlyph) {
        return `<span class="source-badge badge-font" title="字形来源于自定义字体【${esc(customFontName)}】">🔤 字体</span>`;
      } else {
        return `<span class="source-badge badge-svg" title="字形来源于矢量 SVG 引擎直出">⚡ SVG</span>`;
      }
    }

    // 核心字形渲染生成器 (满足需求 1：优先字体，无字形/未上传时使用 SVG，米字格内部 100% 纯净无遮挡)
    // 关键优化：支持服务端单次检索直接返回的内联 SVG 数据，整页 50 个字形零额外网络请求瞬间直出！
    // 事件通过 resultsGrid 委托 + data-copy 处理，不再生成内联 onclick（消除拼接注入面）
    function buildGlyphHtml(char, hexCode, svgData) {
      const cp = char ? char.codePointAt(0) : 0;
      const hasGlyph = customFontActive && customFontGlyphs.has(cp);
      const mzClass = showMizige ? 'with-mizige' : '';
      const safeChar = esc(char);
      const tooltip = hasGlyph
        ? `【${char}】由自定义字体渲染 (点击复制)`
        : `【${char}】由矢量 SVG 渲染 (点击复制)`;

      if (hasGlyph) {
        // 1. 优先使用字体渲染 (内部纯净，不放任何角标)
        return `
          <div class="glyph-display is-font-glyph ${mzClass}" data-copy="${safeChar}" title="${esc(tooltip)}">
            <span class="glyph-text-font">${safeChar}</span>
          </div>
        `;
      } else if (svgData) {
        // 2. 数据库一次性返回内联 SVG：直接内联渲染，整页零额外网络请求！
        //    SVG 来自本地可信字库，需保持原始标签结构不做转义
        return `
          <div class="glyph-display is-svg-glyph ${mzClass}" data-copy="${safeChar}" title="${esc(tooltip)}">
            ${svgData}
          </div>
        `;
      } else {
        // 3. 极罕见生僻字未缓存时，自动降级图片拉取
        const localSvgUrl = `/api/svg?code=${encodeURIComponent(hexCode)}`;
        return `
          <div class="glyph-display is-svg-glyph ${mzClass}" data-copy="${safeChar}" title="${esc(tooltip)}">
            <img class="glyph-svg" src="${localSvgUrl}" alt="${safeChar}" 
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
            <span class="glyph-text-fallback">${safeChar}</span>
          </div>
        `;
      }
    }

    // 综合检索函数 (支持 单独检索框、单独总笔画数、组合检索)
    let searchSeq = 0;   // 请求序号守卫：过期响应直接丢弃，防止慢响应覆盖新结果
    async function doSearch(page = 1) {
      const q = searchInput.value.trim();
      const strokesRaw = strokesInput.value.trim();

      // 笔画输入校验：非法值明确提示，不再静默忽略变成全量检索
      const strokesOk = !strokesRaw ||
        (strokesRaw.length <= 2 && Array.from(strokesRaw).every(c => c >= '0' && c <= '9'));
      if (!strokesOk) {
        statusText.innerText = '笔画数请输入 1~99 的整数';
        return;
      }
      const strokes = strokesRaw;

      // 两者皆空时清空视图
      if (!q && !strokes) {
        resultsGrid.innerHTML = '';
        paginationBar.style.display = 'none';
        statusText.innerText = '输入内容或指定总笔画数以开始检索（支持 9 万+ Unicode CJK 统一表意文字）';
        countText.innerText = '';
        return;
      }

      const seq = ++searchSeq;
      statusText.innerText = '正在检索中...';
      try {
        let apiUrl = `/api/search?page=${page}&page_size=${pageSize}`;
        if (q) apiUrl += `&q=${encodeURIComponent(q)}`;
        if (strokes) apiUrl += `&strokes=${encodeURIComponent(strokes)}`;

        const data = await fetchJson(apiUrl);
        if (seq !== searchSeq) return;   // 已有更新的请求，丢弃本次过期响应

        currentResults = data.results || [];
        currentPage = data.page || 1;
        totalPages = data.total_pages || 0;
        totalCount = data.total_count || 0;

        let modeDesc = `模式: [${data.mode}]`;
        if (q && strokes) {
          modeDesc = `组合检索: [${q}] + [${strokes} 画]`;
        } else if (strokes) {
          modeDesc = `总笔画单独检索: [${strokes} 画]`;
        } else {
          modeDesc = `检索: [${q}]`;
        }

        statusText.innerText = modeDesc;
        countText.innerText = `共 ${totalCount} 条结果 (每页 ${pageSize} 条)`;

        renderCards(currentResults);
        renderPagination();
      } catch (err) {
        if (seq === searchSeq) statusText.innerText = '检索出错：' + err.message;
      }
    }

    function getMatchedVaultGlyphs(query) {
      if (!query) return [];
      const q = query.trim().toLowerCase();
      try {
        const vault = JSON.parse(localStorage.getItem('hanzi_lego_vault') || '[]');
        return vault.filter(v => {
          const py = (v.pinyin || '').toLowerCase();
          const ids = (v.ids || '').toLowerCase();
          const meaning = (v.meaning || '').toLowerCase();
          return py.includes(q) || ids.includes(q) || meaning.includes(q) ||
                 Object.values(v.slots || {}).some(s => s.char && q.includes(s.char));
        });
      } catch (e) {
        return [];
      }
    }

    function renderCards(list) {
      const q = (searchInput.value || '').trim();
      const matchedVault = (currentPage === 1 && q) ? getMatchedVaultGlyphs(q) : [];

      if ((!list || list.length === 0) && matchedVault.length === 0) {
        resultsGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 48px; color: #8c7b70; background:#fff; border-radius:12px; border:1px dashed #ded5c7;">未找到匹配汉字，请尝试更换拆字部件或调整总笔画数</div>';
        return;
      }

      // 1. 自造字卡片 HTML (置顶展示)
      const vaultCardsHtml = matchedVault.map(v => {
        const mzClass = showMizige ? 'with-mizige' : '';
        return `
          <div class="char-card" style="border: 1.5px solid #d35400; background: #fffcf8;">
            <div class="glyph-display is-svg-glyph ${mzClass}" data-copy="${esc(v.ids)}" title="自造字【${esc(v.ids)}】(点击复制)">
              ${v.svgData}
            </div>
            <div class="char-meta">
              <div class="char-header">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="badge-custom-glyph">★ 自创字</span>
                  <span class="source-badge badge-svg" style="background:#fef5e7; color:#d35400;">${esc(v.liushu || '会意')}</span>
                </div>
                <button class="probe-btn" onclick="window.location.href='/lego?load=' + encodeURIComponent('${v.id}');" title="前往汉字乐高编辑此字">🧱 编辑新字</button>
              </div>
              <div class="char-prop">
                <span class="label">结构:</span>
                <b style="color:var(--primary);">${esc(v.ids)}</b>
              </div>
              <div class="char-prop">
                <span class="label">拼音:</span>
                <span class="pinyin-badge" style="background:var(--primary-light); color:var(--primary); font-weight:bold;">${esc(v.pinyin || '无')}</span>
                <span style="font-size:11px; color:#888; margin-left:auto;">${esc(v.author || '')}</span>
              </div>
              <div style="font-size:11px; color:#6d635b; margin-top:4px; line-height:1.4;" title="${esc(v.meaning)}">
                释义: ${esc(v.meaning || '无')}
              </div>
            </div>
          </div>
        `;
      }).join('');

      const standardCardsHtml = list.map(r => {
        const char = r.character || '';
        const hex = r.hex_code || '';
        const ids = r.ids_direct || '独体';
        const rawTokens = r.ids_tokens || '';
        const pinyin = r.pinyin ? `[${r.pinyin}]` : '';
        const strokes = r.total_strokes ? `${r.total_strokes} 画` : '未知';

        // 部件反向穿透交互标签（data-comp + 事件委托，不再拼接内联 onclick）
        const tokensHtml = rawTokens.split(',').map(t => t.trim()).filter(t => t)
          .map(t => `<span class="comp-chip" data-comp="${esc(t)}" title="穿透检索含【${esc(t)}】的汉字">${esc(t)}</span>`)
          .join(' ');

        // 简繁与异体字流变展示
        const trad = r.traditional || '';
        const sem = r.semantic || '';
        const simp = r.simplified || '';

        let variantsHtml = '';
        if (trad) {
          const t0 = trad.split(' ')[0];
          variantsHtml += `<span class="var-tag var-trad" data-comp="${esc(t0)}" title="繁体: ${esc(trad)}">繁: ${esc(t0)}</span>`;
        }
        if (sem) {
          const s0 = sem.split(' ')[0];
          variantsHtml += `<span class="var-tag var-sem" data-comp="${esc(s0)}" title="异体/古字: ${esc(sem)}">异: ${esc(s0)}</span>`;
        }
        if (simp && simp.split(' ')[0] !== char) {
          const p0 = simp.split(' ')[0];
          variantsHtml += `<span class="var-tag var-trad" data-comp="${esc(p0)}" title="简体: ${esc(simp)}">简: ${esc(p0)}</span>`;
        }

        const glyphDisplayHtml = buildGlyphHtml(char, hex, r.svg_data);
        const sourceBadgeHtml = buildSourceBadge(char);

        return `
          <div class="char-card">
            ${glyphDisplayHtml}
            <div class="char-meta">
              <div class="char-header">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="char-code" data-hex="${esc(hex)}" title="点击复制码位">
                    ${esc(hex)}
                  </span>
                  ${sourceBadgeHtml}
                </div>
                <button class="probe-btn" data-char="${esc(char)}" data-hex="${esc(hex)}" title="打开血缘探针与谱系">🌳 血缘探针</button>
              </div>
              <div class="char-prop">
                <span class="label">结构:</span>
                <b>${esc(ids)}</b>
                ${tokensHtml ? `<span style="margin-left:4px;">${tokensHtml}</span>` : ''}
              </div>
              <div class="char-prop">
                <span class="label">属性:</span>
                <span class="stroke-badge">${esc(strokes)}</span>
                ${pinyin ? `<span class="pinyin-badge">${esc(pinyin)}</span>` : ''}
              </div>
              ${variantsHtml ? `<div class="variants-line">${variantsHtml}</div>` : ''}
            </div>
          </div>
        `;
      }).join('');

      resultsGrid.innerHTML = vaultCardsHtml + standardCardsHtml;
    }

    // 结果网格事件委托：统一处理字形复制 / 码位复制 / 血缘探针 / 部件穿透
    resultsGrid.addEventListener('click', (e) => {
      const glyph = e.target.closest('.glyph-display');
      if (glyph && glyph.dataset.copy) {
        navigator.clipboard.writeText(glyph.dataset.copy)
          .then(() => showToast('已复制字符: ' + glyph.dataset.copy))
          .catch(() => showToast('复制失败，请手动选择'));
        return;
      }
      const codeEl = e.target.closest('.char-code');
      if (codeEl && codeEl.dataset.hex) {
        navigator.clipboard.writeText(codeEl.dataset.hex)
          .then(() => showToast('已复制码位: ' + codeEl.dataset.hex))
          .catch(() => showToast('复制失败，请手动选择'));
        return;
      }
      const probe = e.target.closest('.probe-btn');
      if (probe && probe.dataset.char) {
        openFamilyModal(probe.dataset.char, probe.dataset.hex || '');
        return;
      }
      const chip = e.target.closest('.comp-chip, .var-tag');
      if (chip && chip.dataset.comp) {
        drillComponent(chip.dataset.comp);
      }
    });

    function renderPagination() {
      if (totalPages <= 1) {
        paginationBar.style.display = 'none';
        return;
      }

      paginationBar.style.display = 'flex';
      pageInfoText.innerText = `第 ${currentPage} / ${totalPages} 页 (共 ${totalCount} 条)`;
      jumpPageInput.max = totalPages;
      jumpPageInput.value = currentPage;

      prevPageBtn.disabled = (currentPage <= 1);
      nextPageBtn.disabled = (currentPage >= totalPages);
    }

    function changePage(newPage) {
      if (newPage < 1 || newPage > totalPages || newPage === currentPage) return;
      doSearch(newPage);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function jumpToPage() {
      let p = parseInt(jumpPageInput.value, 10);
      if (isNaN(p)) return;
      if (p < 1) p = 1;
      if (p > totalPages) p = totalPages;
      changePage(p);
    }

    function triggerAutoSearch() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentPage = 1;
        doSearch(1);
      }, 250);
    }

    searchInput.addEventListener('input', triggerAutoSearch);
    strokesInput.addEventListener('input', triggerAutoSearch);

    searchBtn.addEventListener('click', () => {
      currentPage = 1;
      doSearch(1);
    });

    resetBtn.addEventListener('click', () => {
      searchInput.value = '';
      strokesInput.value = '';
      updateClearIcons();
      currentPage = 1;
      doSearch(1);
      searchInput.focus();
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(debounceTimer);
        currentPage = 1;
        doSearch(1);
      }
    });

    strokesInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(debounceTimer);
        currentPage = 1;
        doSearch(1);
      }
    });

    // 模态弹窗交互
    async function openFamilyModal(char, hex) {
      const cp = char ? char.codePointAt(0) : 0;
      const hasGlyph = customFontActive && customFontGlyphs.has(cp);
      const sourceBadgeHtml = buildSourceBadge(char);

      modalTitle.innerHTML = `【 ${char} 】 ${sourceBadgeHtml}`;
      modalMeta.innerText = `Unicode: ${hex} | 正在调取家族图谱...`;
      
      // 大字纯净展示：优先字体，降级先用加载动画
      if (hasGlyph) {
        modalGlyph.innerHTML = `<span class="glyph-text-font" style="font-size:68px; line-height:98px;">${char}</span>`;
      } else {
        modalGlyph.innerHTML = `<span style="font-size:13px; color:#999;">加载中...</span>`;
      }
      modalParents.innerHTML = '加载中...';
      modalVariants.innerHTML = '加载中...';
      modalDescendants.innerHTML = '加载中...';

      familyModal.style.display = 'flex';

      try {
        const data = await fetchJson(`/api/family?code=${encodeURIComponent(hex)}`);

        // 判空守卫：后端已改为 404，此处兜底防 200+空体导致渲染崩溃
        if (!data || !data.root) {
          modalMeta.innerText = `未找到 ${hex} 对应的谱系数据`;
          modalParents.innerHTML = '<span style="color:#999;">无谱系数据</span>';
          modalVariants.innerHTML = '<span style="color:#999;">无谱系数据</span>';
          modalDescendants.innerHTML = '<span style="color:#999;">无谱系数据</span>';
          return;
        }

        renderFamilyTree(data);

        // 如果未命中自定义字体，优先采用后端一次性返回的内联 svg_data
        if (!hasGlyph) {
          if (data.root.svg_data) {
            modalGlyph.innerHTML = data.root.svg_data;
          } else {
            modalGlyph.innerHTML = `
              <img class="glyph-svg" src="/api/svg?code=${encodeURIComponent(hex)}" alt="${esc(char)}" 
                   onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
              <span class="glyph-text-fallback" style="font-size:60px;">${esc(char)}</span>
            `;
          }
        }
      } catch (err) {
        modalMeta.innerText = `${hex} 谱系加载失败`;
        modalParents.innerHTML = '<span style="color:#999;">无谱系数据</span>';
        modalVariants.innerHTML = '请求失败：' + esc(err.message);
        modalDescendants.innerHTML = '<span style="color:#999;">无谱系数据</span>';
      }
    }

    function closeFamilyModal() {
      familyModal.style.display = 'none';
    }

    // 设置模态弹窗控制
    const settingsModal = document.getElementById('settingsModal');
    function openSettingsModal() {
      settingsModal.style.display = 'flex';
    }
    function closeSettingsModal() {
      settingsModal.style.display = 'none';
    }

    function renderFamilyTree(fam) {
      const root = fam.root;
      if (!root) return;   // 防御：调用方已判空，此处再兜一层
      modalMeta.innerText = `Unicode: ${root.hex_code} | 结构: ${root.ids_direct || '独体'} | 总笔画: ${root.total_strokes || '未知'} 画 | ${root.pinyin ? '拼音: ' + root.pinyin : ''}`;

      // 1. 父部件渲染 (直接展示部件纯净小字形或SVG)
      if (!fam.parents || fam.parents.length === 0) {
        modalParents.innerHTML = '<span style="color:#999;">独体构字，无父级组合部件</span>';
      } else {
        modalParents.innerHTML = fam.parents.map(p => {
          const char = typeof p === 'object' ? p.character : p;
          const hex = (typeof p === 'object' && p.hex_code) ? p.hex_code : ('U+' + char.codePointAt(0).toString(16).toUpperCase());
          const sub = (typeof p === 'object' && p.pinyin) ? p.pinyin : '构架构件';
          const pCp = char.codePointAt(0);
          const pHasFont = customFontActive && customFontGlyphs.has(pCp);
          const safeChar = esc(char);

          let pIcon = '';
          if (pHasFont) {
            pIcon = `<span style="font-size:26px; font-family:'UserCustomFont', var(--font-serif);">${safeChar}</span>`;
          } else {
            pIcon = `<img src="/api/svg?code=${encodeURIComponent(hex)}" alt="${safeChar}" style="width:28px; height:28px; object-fit:contain;" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" /><span style="display:none; font-size:20px;">${safeChar}</span>`;
          }

          return `
            <div class="parent-pill" data-comp="${safeChar}" title="点击穿透检索【${safeChar}】(${esc(hex)})家族">
              <div style="width:30px; height:30px; display:flex; align-items:center; justify-content:center;">
                ${pIcon}
              </div>
              <div>
                <b style="font-size:16px;">${safeChar}</b>
                <div style="font-size:11px; color:#888;">${esc(sub)}</div>
              </div>
            </div>
          `;
        }).join('');
      }

      // 2. 简繁与异体字流变渲染
      let varRows = [];
      if (root.traditional) {
        varRows.push(`<div><b>传统繁体:</b> <span style="color:#d35400;">${esc(root.traditional)}</span></div>`);
      }
      if (root.simplified) {
        varRows.push(`<div><b>规范简体:</b> <span style="color:#27ae60;">${esc(root.simplified)}</span></div>`);
      }
      if (root.semantic) {
        varRows.push(`<div><b>异体 / 古体字:</b> <span style="color:#8e44ad;">${esc(root.semantic)}</span></div>`);
      }
      if (root.z_variant) {
        varRows.push(`<div><b>笔形变体:</b> <span style="color:#2980b9;">${esc(root.z_variant)}</span></div>`);
      }
      modalVariants.innerHTML = varRows.length > 0 ? varRows.join('') : '<span style="color:#999;">该字无直接简繁或语义异体流变记录</span>';

      // 3. 下游衍生后裔渲染 (直接优先使用内联 svg_data，零网络请求)
      if (!fam.descendants || fam.descendants.length === 0) {
        modalDescendants.innerHTML = '<span style="color:#999;">暂未发现以此字为构件的衍生字</span>';
      } else {
        modalDescendants.innerHTML = fam.descendants.map(d => {
          const subText = d.pinyin || (d.total_strokes ? `${d.total_strokes}画` : d.hex_code);
          const cp = d.character.codePointAt(0);
          const hasFont = customFontActive && customFontGlyphs.has(cp);
          const safeChar = esc(d.character);

          let innerBox = '';
          if (hasFont) {
            innerBox = `<span style="font-size:30px; font-family:'UserCustomFont', var(--font-serif); line-height:44px;">${safeChar}</span>`;
          } else if (d.svg_data) {
            innerBox = d.svg_data;
          } else {
            innerBox = `
              <img src="/api/svg?code=${encodeURIComponent(d.hex_code)}" alt="${safeChar}" 
                   onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
              <div style="display:none; font-size:24px;">${safeChar}</div>
            `;
          }

          return `
            <div class="descendant-card" data-char="${safeChar}" data-hex="${esc(d.hex_code)}" title="${safeChar} (${esc(d.hex_code)})&#10;拼音: ${esc(d.pinyin || '无')}&#10;笔画: ${esc(d.total_strokes || '未知')}画&#10;结构: ${esc(d.ids_direct || '未知')}&#10;点击探针此字">
              <div class="descendant-glyph-box">
                ${innerBox}
              </div>
              <span class="descendant-meta">${esc(subText)}</span>
            </div>
          `;
        }).join('');
      }
    }

    // 血缘弹窗事件委托：父部件穿透 / 后裔字探针
    modalParents.addEventListener('click', (e) => {
      const pill = e.target.closest('.parent-pill');
      if (pill && pill.dataset.comp) {
        closeFamilyModal();
        drillComponent(pill.dataset.comp);
      }
    });

    modalDescendants.addEventListener('click', (e) => {
      const card = e.target.closest('.descendant-card');
      if (card && card.dataset.char) {
        openFamilyModal(card.dataset.char, card.dataset.hex || '');
      }
    });

    // ESC 关闭任意已打开的模态弹窗
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const legoCardModal = document.getElementById('legoCardModal');
      if (legoCardModal && legoCardModal.style.display === 'flex') { closeCardModal(); return; }
      const legoModal = document.getElementById('legoModal');
      if (legoModal && legoModal.style.display === 'flex') { closeLegoModal(); return; }
      if (familyModal.style.display === 'flex') { closeFamilyModal(); return; }
      if (settingsModal.style.display === 'flex') { closeSettingsModal(); return; }
    });

    // 汉字检索主站初始化运行
    if (typeof initToolbox === 'function') initToolbox();
    if (typeof initFontSystem === 'function') initFontSystem();

    // 默认检索演示 "回"
    if (typeof searchInput !== 'undefined' && searchInput) {
      searchInput.value = "回";
      updateClearIcons();
      savedCursorStart = savedCursorEnd = searchInput.value.length;
      doSearch(1);
    }
