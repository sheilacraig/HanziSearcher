/* ==========================================================================
       🧱 汉字乐高核心引擎与交互逻辑
       ========================================================================== */

    // HTML 转义：防止 XSS 注入
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    // 统一 fetch 封装：检查 HTTP 状态码
    async function fetchJson(url, opts) {
      const res = await fetch(url, opts);
      if (!res.ok) {
        let detail = '';
        try { const j = await res.json(); detail = j.error || ''; } catch (e) {}
        throw new Error(`HTTP ${res.status}${detail ? '：' + detail : ''}`);
      }
      return res.json();
    }

    // 全局轻提示浮层
    let toastTimer = null;
    function showToast(msg) {
      const toast = document.getElementById('copyToast');
      if (!toast) return;
      toast.innerText = msg;
      toast.style.display = 'block';
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => { toast.style.display = 'none'; }, 1600);
    }

    const LEGO_LAYOUTS = {
      'left-right': {
        name: '左右结构',
        idc: '⿰',
        slots: {
          A: { label: '左部', x: 8, y: 15, w: 88, h: 170, defaultScaleX: 0.90, defaultScaleY: 0.94 },
          B: { label: '右部', x: 104, y: 15, w: 88, h: 170, defaultScaleX: 0.90, defaultScaleY: 0.94 }
        }
      },
      'top-bottom': {
        name: '上下结构',
        idc: '⿱',
        slots: {
          A: { label: '上部', x: 15, y: 8, w: 170, h: 88, defaultScaleX: 0.94, defaultScaleY: 0.90 },
          B: { label: '下部', x: 15, y: 104, w: 170, h: 88, defaultScaleX: 0.94, defaultScaleY: 0.90 }
        }
      },
      'left-mid-right': {
        name: '左中右结构',
        idc: '⿲',
        slots: {
          A: { label: '左部', x: 6, y: 15, w: 58, h: 170, defaultScaleX: 0.90, defaultScaleY: 0.94 },
          B: { label: '中部', x: 71, y: 15, w: 58, h: 170, defaultScaleX: 0.90, defaultScaleY: 0.94 },
          C: { label: '右部', x: 136, y: 15, w: 58, h: 170, defaultScaleX: 0.90, defaultScaleY: 0.94 }
        }
      },
      'top-mid-bottom': {
        name: '上中下结构',
        idc: '⿳',
        slots: {
          A: { label: '上部', x: 15, y: 6, w: 170, h: 58, defaultScaleX: 0.94, defaultScaleY: 0.90 },
          B: { label: '中部', x: 15, y: 71, w: 170, h: 58, defaultScaleX: 0.94, defaultScaleY: 0.90 },
          C: { label: '下部', x: 15, y: 136, w: 170, h: 58, defaultScaleX: 0.94, defaultScaleY: 0.90 }
        }
      },
      'surround': {
        name: '全包围结构',
        idc: '⿴',
        slots: {
          A: { label: '外框', x: 10, y: 10, w: 180, h: 180, defaultScaleX: 0.98, defaultScaleY: 0.98, defaultChar: '囗' },
          B: { label: '内芯', x: 46, y: 46, w: 108, h: 108, defaultScaleX: 0.90, defaultScaleY: 0.90 }
        }
      },
      'triplet': {
        name: '品字形三叠字',
        idc: '品',
        slots: {
          A: { label: '顶部', x: 55, y: 8, w: 90, h: 88, defaultScaleX: 0.90, defaultScaleY: 0.90 },
          B: { label: '左下', x: 8, y: 104, w: 90, h: 88, defaultScaleX: 0.90, defaultScaleY: 0.90 },
          C: { label: '右下', x: 102, y: 104, w: 90, h: 88, defaultScaleX: 0.90, defaultScaleY: 0.90 }
        }
      },
      'quad': {
        name: '四叠字',
        idc: '㗊',
        slots: {
          A: { label: '左上', x: 10, y: 10, w: 86, h: 86, defaultScaleX: 0.90, defaultScaleY: 0.90 },
          B: { label: '右上', x: 104, y: 10, w: 86, h: 86, defaultScaleX: 0.90, defaultScaleY: 0.90 },
          C: { label: '左下', x: 10, y: 104, w: 86, h: 86, defaultScaleX: 0.90, defaultScaleY: 0.90 },
          D: { label: '右下', x: 104, y: 104, w: 86, h: 86, defaultScaleX: 0.90, defaultScaleY: 0.90 }
        }
      },
      'freeform': {
        name: '自由重叠',
        idc: '⿻',
        slots: {
          A: { label: '底图层', x: 15, y: 15, w: 170, h: 170, defaultScaleX: 0.95, defaultScaleY: 0.95 },
          B: { label: '顶图层', x: 25, y: 25, w: 150, h: 150, defaultScaleX: 0.90, defaultScaleY: 0.90 }
        }
      }
    };

    let currentLegoLayout = 'left-right';
    let activeSlotKey = 'A';
    let legoSlotsData = {};
    let slotSubdivisions = {}; // 记录每个顶级插槽的自由二级骨架: { A: 'top-bottom', B: 'triplet' }
    let cachedPresetRadicals = null;
    let currentLegoCategory = '自然天地';

    // 获取当前布局下经用户自由细分展开后的实际生效插槽映射
    function getEffectiveSlots() {
      const tpl = LEGO_LAYOUTS[currentLegoLayout];
      if (!tpl) return {};
      const effective = {};

      Object.keys(tpl.slots).forEach(slotKey => {
        const pDef = tpl.slots[slotKey];
        const subType = slotSubdivisions[slotKey] || 'none';

        if (subType === 'left-right') {
          // 左右二分骨架
          const gap = 2;
          const halfW = (pDef.w - gap) / 2;
          effective[`${slotKey}1`] = {
            label: `${pDef.label}·左`,
            parentKey: slotKey,
            subType: 'left-right',
            subIndex: 1,
            x: pDef.x,
            y: pDef.y,
            w: halfW,
            h: pDef.h,
            defaultScaleX: 0.90,
            defaultScaleY: 0.94
          };
          effective[`${slotKey}2`] = {
            label: `${pDef.label}·右`,
            parentKey: slotKey,
            subType: 'left-right',
            subIndex: 2,
            x: pDef.x + halfW + gap,
            y: pDef.y,
            w: halfW,
            h: pDef.h,
            defaultScaleX: 0.90,
            defaultScaleY: 0.94
          };
        } else if (subType === 'top-bottom') {
          // 上下二分骨架
          const gap = 2;
          const halfH = (pDef.h - gap) / 2;
          effective[`${slotKey}1`] = {
            label: `${pDef.label}·上`,
            parentKey: slotKey,
            subType: 'top-bottom',
            subIndex: 1,
            x: pDef.x,
            y: pDef.y,
            w: pDef.w,
            h: halfH,
            defaultScaleX: 0.94,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}2`] = {
            label: `${pDef.label}·下`,
            parentKey: slotKey,
            subType: 'top-bottom',
            subIndex: 2,
            x: pDef.x,
            y: pDef.y + halfH + gap,
            w: pDef.w,
            h: halfH,
            defaultScaleX: 0.94,
            defaultScaleY: 0.90
          };
        } else if (subType === 'left-mid-right') {
          // 左中右三分骨架
          const gap = 2;
          const colW = (pDef.w - gap * 2) / 3;
          effective[`${slotKey}1`] = {
            label: `${pDef.label}·左`,
            parentKey: slotKey,
            subType: 'left-mid-right',
            subIndex: 1,
            x: pDef.x,
            y: pDef.y,
            w: colW,
            h: pDef.h,
            defaultScaleX: 0.90,
            defaultScaleY: 0.94
          };
          effective[`${slotKey}2`] = {
            label: `${pDef.label}·中`,
            parentKey: slotKey,
            subType: 'left-mid-right',
            subIndex: 2,
            x: pDef.x + colW + gap,
            y: pDef.y,
            w: colW,
            h: pDef.h,
            defaultScaleX: 0.90,
            defaultScaleY: 0.94
          };
          effective[`${slotKey}3`] = {
            label: `${pDef.label}·右`,
            parentKey: slotKey,
            subType: 'left-mid-right',
            subIndex: 3,
            x: pDef.x + (colW + gap) * 2,
            y: pDef.y,
            w: colW,
            h: pDef.h,
            defaultScaleX: 0.90,
            defaultScaleY: 0.94
          };
        } else if (subType === 'top-mid-bottom') {
          // 上中下三分骨架
          const gap = 2;
          const rowH = (pDef.h - gap * 2) / 3;
          effective[`${slotKey}1`] = {
            label: `${pDef.label}·上`,
            parentKey: slotKey,
            subType: 'top-mid-bottom',
            subIndex: 1,
            x: pDef.x,
            y: pDef.y,
            w: pDef.w,
            h: rowH,
            defaultScaleX: 0.94,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}2`] = {
            label: `${pDef.label}·中`,
            parentKey: slotKey,
            subType: 'top-mid-bottom',
            subIndex: 2,
            x: pDef.x,
            y: pDef.y + rowH + gap,
            w: pDef.w,
            h: rowH,
            defaultScaleX: 0.94,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}3`] = {
            label: `${pDef.label}·下`,
            parentKey: slotKey,
            subType: 'top-mid-bottom',
            subIndex: 3,
            x: pDef.x,
            y: pDef.y + (rowH + gap) * 2,
            w: pDef.w,
            h: rowH,
            defaultScaleX: 0.94,
            defaultScaleY: 0.90
          };
        } else if (subType === 'triplet') {
          // 品字形/三叠骨架 (顶槽水平严格居中，下方两槽对称并列)
          const gap = 2;
          const subW = (pDef.w - gap) / 2;
          const subH = (pDef.h - gap) / 2;
          effective[`${slotKey}1`] = {
            label: `${pDef.label}·顶`,
            parentKey: slotKey,
            subType: 'triplet',
            subIndex: 1,
            x: pDef.x + (pDef.w - subW) / 2,
            y: pDef.y,
            w: subW,
            h: subH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}2`] = {
            label: `${pDef.label}·左下`,
            parentKey: slotKey,
            subType: 'triplet',
            subIndex: 2,
            x: pDef.x,
            y: pDef.y + subH + gap,
            w: subW,
            h: subH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}3`] = {
            label: `${pDef.label}·右下`,
            parentKey: slotKey,
            subType: 'triplet',
            subIndex: 3,
            x: pDef.x + subW + gap,
            y: pDef.y + subH + gap,
            w: subW,
            h: subH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
        } else if (subType === 'surround') {
          // 全包围骨架 (内芯同心居中)
          const innerW = pDef.w * 0.60;
          const innerH = pDef.h * 0.60;
          effective[`${slotKey}1`] = {
            label: `${pDef.label}·外框`,
            parentKey: slotKey,
            subType: 'surround',
            subIndex: 1,
            x: pDef.x,
            y: pDef.y,
            w: pDef.w,
            h: pDef.h,
            defaultScaleX: 0.98,
            defaultScaleY: 0.98,
            defaultChar: '囗'
          };
          effective[`${slotKey}2`] = {
            label: `${pDef.label}·内芯`,
            parentKey: slotKey,
            subType: 'surround',
            subIndex: 2,
            x: pDef.x + (pDef.w - innerW) / 2,
            y: pDef.y + (pDef.h - innerH) / 2,
            w: innerW,
            h: innerH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
        } else if (subType === 'quad') {
          // 四叠字骨架 (四宫格四象限对称居中)
          const gap = 2;
          const subW = (pDef.w - gap) / 2;
          const subH = (pDef.h - gap) / 2;
          effective[`${slotKey}1`] = {
            label: `${pDef.label}·左上`,
            parentKey: slotKey,
            subType: 'quad',
            subIndex: 1,
            x: pDef.x,
            y: pDef.y,
            w: subW,
            h: subH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}2`] = {
            label: `${pDef.label}·右上`,
            parentKey: slotKey,
            subType: 'quad',
            subIndex: 2,
            x: pDef.x + subW + gap,
            y: pDef.y,
            w: subW,
            h: subH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}3`] = {
            label: `${pDef.label}·左下`,
            parentKey: slotKey,
            subType: 'quad',
            subIndex: 3,
            x: pDef.x,
            y: pDef.y + subH + gap,
            w: subW,
            h: subH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
          effective[`${slotKey}4`] = {
            label: `${pDef.label}·右下`,
            parentKey: slotKey,
            subType: 'quad',
            subIndex: 4,
            x: pDef.x + subW + gap,
            y: pDef.y + subH + gap,
            w: subW,
            h: subH,
            defaultScaleX: 0.90,
            defaultScaleY: 0.90
          };
        } else {
          // 独体单部件
          effective[slotKey] = {
            ...pDef,
            parentKey: slotKey,
            subType: 'none',
            defaultScaleX: pDef.defaultScaleX || 0.92,
            defaultScaleY: pDef.defaultScaleY || 0.92
          };
        }
      });

      return effective;
    }

    // 初始化汉字乐高
    function initLegoStudio() {
      if (Object.keys(legoSlotsData).length === 0) {
        applyLayoutSlots('left-right', false);
        setSlotComponent('A', '日', null);
        setSlotComponent('B', '木', null);
        document.getElementById('legoPinyin').value = 'miáo';
        document.getElementById('legoMeaning').value = '晨光初起，林木向阳，生命勃发之意。';
      }
      loadPresetRadicals();
      updateVaultBadge();
      renderLegoCanvas();
      renderSlotTabs();
      updateTransformPanelUI();
      updateLegoIds();
    }

    // 应用并重置插槽结构
    function applyLayoutSlots(layoutKey, keepExisting = true) {
      currentLegoLayout = layoutKey;
      const tpl = LEGO_LAYOUTS[layoutKey];
      if (!tpl) return;

      // 切换一级骨架时，清理不适用的细分配置
      if (!keepExisting) {
        slotSubdivisions = {};
      } else {
        const validKeys = Object.keys(tpl.slots);
        const cleanedSub = {};
        validKeys.forEach(k => {
          if (slotSubdivisions[k]) cleanedSub[k] = slotSubdivisions[k];
        });
        slotSubdivisions = cleanedSub;
      }

      const effSlots = getEffectiveSlots();
      const newSlotsData = {};

      Object.keys(effSlots).forEach(slotKey => {
        const slotDef = effSlots[slotKey];
        if (keepExisting && legoSlotsData[slotKey]) {
          newSlotsData[slotKey] = { ...legoSlotsData[slotKey] };
        } else {
          newSlotsData[slotKey] = {
            char: slotDef.defaultChar || '',
            svg: '',
            offsetX: 0,
            offsetY: 0,
            scaleX: 1.0,
            scaleY: 1.0,
            rotate: 0,
            flipX: false
          };
          if (slotDef.defaultChar) {
            fetchComponentSvg(slotDef.defaultChar).then(svg => {
              if (newSlotsData[slotKey]) {
                newSlotsData[slotKey].svg = svg;
                renderLegoCanvas();
              }
            });
          }
        }
      });

      legoSlotsData = newSlotsData;
      if (!legoSlotsData[activeSlotKey]) {
        activeSlotKey = Object.keys(effSlots)[0] || 'A';
      }
    }

    // 细分当前激活插槽为任意自由骨架或恢复独体
    function changeSlotSubdivision(subType) {
      const eff = getEffectiveSlots();
      const currentSlotDef = eff[activeSlotKey];
      const parentKey = currentSlotDef ? (currentSlotDef.parentKey || activeSlotKey) : activeSlotKey;

      const oldParentChar = legoSlotsData[parentKey]?.char || '';
      const oldChildChar = legoSlotsData[`${parentKey}1`]?.char || '';

      slotSubdivisions[parentKey] = subType;

      const newEff = getEffectiveSlots();
      if (!newEff[activeSlotKey]) {
        activeSlotKey = Object.keys(newEff).find(k => k.startsWith(parentKey)) || Object.keys(newEff)[0];
      }

      // 确保新生成的子槽位在数据字典中初始化
      Object.keys(newEff).forEach(k => {
        if (!legoSlotsData[k]) {
          const slotDef = newEff[k];
          legoSlotsData[k] = {
            char: slotDef.defaultChar || '',
            svg: '',
            offsetX: 0,
            offsetY: 0,
            scaleX: 1.0,
            scaleY: 1.0,
            rotate: 0,
            flipX: false
          };
          if (slotDef.defaultChar) {
            fetchComponentSvg(slotDef.defaultChar).then(svg => {
              if (legoSlotsData[k]) {
                legoSlotsData[k].svg = svg;
                renderLegoCanvas();
              }
            });
          }
        }
      });

      // 平滑继承字符零件：拆分时把原单部件平移至首个子槽；还原独体时从首个子槽移回
      if (subType !== 'none' && oldParentChar && !legoSlotsData[`${parentKey}1`].char) {
        setSlotComponent(`${parentKey}1`, oldParentChar, legoSlotsData[parentKey]?.svg || null);
      } else if (subType === 'none' && oldChildChar && !legoSlotsData[parentKey].char) {
        setSlotComponent(parentKey, oldChildChar, legoSlotsData[`${parentKey}1`]?.svg || null);
      }

      renderSlotTabs();
      renderLegoCanvas();
      updateTransformPanelUI();
      updateLegoIds();

      const subLabelMap = {
        'none': '独体部件 (默认)',
        'left-right': '左右结构 (⿰)',
        'top-bottom': '上下结构 (⿱)',
        'left-mid-right': '左中右结构 (⿲)',
        'top-mid-bottom': '上中下结构 (⿳)',
        'triplet': '品字形/三叠 (品)',
        'surround': '全包围结构 (⿴)',
        'quad': '四叠字结构 (㗊)'
      };
      const subLabel = subLabelMap[subType] || subType;
      showToast(`已将槽位【${parentKey}】骨架设置为: ${subLabel}`);
    }

    // 切换结构骨架模板
    function switchLegoLayout(layoutKey, btnEl) {
      if (!LEGO_LAYOUTS[layoutKey]) return;
      document.querySelectorAll('#legoTemplatesBar .lego-tpl-btn').forEach(b => b.classList.remove('active'));
      if (btnEl) btnEl.classList.add('active');

      applyLayoutSlots(layoutKey, true);
      renderSlotTabs();
      renderLegoCanvas();
      updateTransformPanelUI();
      updateLegoIds();
    }

    // 辅助线网格切换
    function switchLegoGridGuide(guideType, btnEl) {
      const board = document.getElementById('legoArtboard');
      board.classList.remove('with-mizige', 'with-jiugongge');
      if (guideType === 'mizige') board.classList.add('with-mizige');
      else if (guideType === 'jiugongge') board.classList.add('with-jiugongge');

      document.querySelectorAll('.lego-guide-switch .guide-btn').forEach(b => b.classList.remove('active'));
      if (btnEl) btnEl.classList.add('active');
    }

    // 渲染插槽选择 Tab
    function renderSlotTabs() {
      const container = document.getElementById('slotSelectTabs');
      const effSlots = getEffectiveSlots();
      if (!container) return;

      container.innerHTML = Object.keys(effSlots).map(k => {
        const slotDef = effSlots[k];
        const data = legoSlotsData[k] || {};
        const charLabel = data.char ? `【${esc(data.char)}】` : '';
        const activeClass = k === activeSlotKey ? 'active' : '';
        return `
          <button class="slot-tab ${activeClass}" onclick="selectActiveSlot('${k}')" title="${slotDef.label}">
            ${k} ${charLabel}
          </button>
        `;
      }).join('');
    }

    // 选择当前激活插槽
    function selectActiveSlot(slotKey) {
      activeSlotKey = slotKey;
      renderSlotTabs();
      renderSlotIndicators();
      updateTransformPanelUI();
    }

    // 从服务端获取单部件 SVG
    async function fetchComponentSvg(char) {
      try {
        const res = await fetch(`/api/lego/svg?char=${encodeURIComponent(char)}`);
        if (res.ok) {
          return await res.text();
        }
      } catch (e) {
        console.warn('获取部件 SVG 失败:', char, e);
      }
      return '';
    }

    // 设置当前槽位部件
    async function setSlotComponent(slotKey, char, svgContent) {
      if (!legoSlotsData[slotKey]) return;
      legoSlotsData[slotKey].char = char;

      if (svgContent) {
        legoSlotsData[slotKey].svg = svgContent;
      } else {
        const svg = await fetchComponentSvg(char);
        if (legoSlotsData[slotKey] && legoSlotsData[slotKey].char === char) {
          legoSlotsData[slotKey].svg = svg;
        }
      }

      renderLegoCanvas();
      renderSlotTabs();
      updateTransformPanelUI();
      updateLegoIds();
    }

    // 汉字拆字机
    async function disassembleInputChar() {
      const input = document.getElementById('legoCharInput');
      const char = (input.value || '').trim();
      if (!char) {
        showToast('请输入要拆解的汉字');
        return;
      }

      const resultsBox = document.getElementById('legoDisassembleResults');
      resultsBox.innerHTML = '<span class="lego-empty-tip">正在拆解构架构件...</span>';

      try {
        const data = await fetchJson(`/api/lego/disassemble?char=${encodeURIComponent(char)}`);
        const comps = data.components || [];

        if (comps.length === 0) {
          resultsBox.innerHTML = '<span class="lego-empty-tip">未解析出独立部件</span>';
          return;
        }

        resultsBox.innerHTML = comps.map(c => {
          const safeC = esc(c.char);
          return `
            <div class="lego-comp-brick" style="width:48px; height:48px;" 
                 onclick="putComponentToActiveSlot('${safeC}')" 
                 title="点击放入插槽 ${activeSlotKey} (${safeC})">
              <div class="brick-glyph">
                ${c.svg_data ? c.svg_data : `<span>${safeC}</span>`}
              </div>
              <span class="brick-char-label">${safeC}</span>
            </div>
          `;
        }).join('');
      } catch (err) {
        resultsBox.innerHTML = `<span class="lego-empty-tip" style="color:#c0392b;">拆解失败: ${esc(err.message)}</span>`;
      }
    }

    // 用户自定义单字作零件
    function addCustomComponent() {
      const input = document.getElementById('legoCustomCompInput');
      const char = (input.value || '').trim();
      if (!char) return;
      putComponentToActiveSlot(char[0]);
      input.value = '';
    }

    // 放入当前激活插槽
    function putComponentToActiveSlot(char) {
      setSlotComponent(activeSlotKey, char, null);
      showToast(`已放入插槽 ${activeSlotKey}: 【${char}】`);
    }

    // 加载常用部首积木库
    async function loadPresetRadicals() {
      const grid = document.getElementById('legoBricksGrid');
      if (cachedPresetRadicals) {
        renderPresetRadicals();
        return;
      }
      grid.innerHTML = '<span class="lego-empty-tip">加载优质部首积木库...</span>';
      try {
        cachedPresetRadicals = await fetchJson('/api/lego/radicals');
        renderPresetRadicals();
      } catch (err) {
        grid.innerHTML = '<span class="lego-empty-tip">部首库加载失败</span>';
      }
    }

    // 切换部首分类
    function switchRadicalCategory(cat, btnEl) {
      currentLegoCategory = cat;
      document.querySelectorAll('#legoCategoryTabs .lego-tab').forEach(b => b.classList.remove('active'));
      if (btnEl) btnEl.classList.add('active');
      renderPresetRadicals();
    }

    function renderPresetRadicals() {
      const grid = document.getElementById('legoBricksGrid');
      if (!cachedPresetRadicals || !grid) return;
      const list = cachedPresetRadicals[currentLegoCategory] || [];

      grid.innerHTML = list.map(item => {
        const safeC = esc(item.char);
        return `
          <div class="lego-comp-brick" onclick="putComponentToActiveSlot('${safeC}')" title="放入插槽 ${activeSlotKey} (${safeC})">
            <div class="brick-glyph">
              ${item.svg_data ? item.svg_data : `<span>${safeC}</span>`}
            </div>
            <span class="brick-char-label">${safeC}</span>
          </div>
        `;
      }).join('');
    }

    // 提取 SVG 内部真实路径内容
    function extractInnerSvg(svgStr) {
      if (!svgStr) return '';
      const m = svgStr.match(/<svg[^>]*>([\s\S]*?)<\/svg>/i);
      return m ? m[1] : svgStr;
    }

    // 核心：在 200x200 矢量舞台中渲染各插槽部件（包含经细分后的子插槽）
    function renderLegoCanvas() {
      const container = document.getElementById('legoSlotsContainer');
      const effSlots = getEffectiveSlots();
      if (!container) return;

      let slotsSvgHtml = '';

      Object.keys(effSlots).forEach(slotKey => {
        const slotDef = effSlots[slotKey];
        const data = legoSlotsData[slotKey];
        if (!data || !data.char) return;

        // 1. 槽位物理几何中心计算 (精确绝对居中定位)
        const slotCenterX = slotDef.x + slotDef.w / 2;
        const slotCenterY = slotDef.y + slotDef.h / 2;

        // 2. 叠加上用户的微调偏移
        const targetCenterX = slotCenterX + (data.offsetX || 0);
        const targetCenterY = slotCenterY + (data.offsetY || 0);

        // 3. 计算基于槽位实际物理尺寸的适配缩放比 (四周留白约 6~8%，保证呼吸感)
        const baseScaleX = (slotDef.w / 200) * (slotDef.defaultScaleX || 0.92);
        const baseScaleY = (slotDef.h / 200) * (slotDef.defaultScaleY || 0.92);

        const finalScaleX = baseScaleX * (data.scaleX || 1.0) * (data.flipX ? -1 : 1);
        const finalScaleY = baseScaleY * (data.scaleY || 1.0);
        const rot = data.rotate || 0;

        // 4. 精确几何中心锚点变换：
        // SVG 矩阵应用顺序（右到左运算）：
        // - translate(-100, -100): 将 200x200 标准字形中心移动至局部原点 (0, 0)
        // - scale(finalScaleX, finalScaleY): 以自身几何中心为基准向四周等比缩放或翻转
        // - rotate(rot): 以自身几何中心为轴心自转
        // - translate(targetCenterX, targetCenterY): 精确直接定位至当前插槽的物理几何中心
        let transformAttr = `translate(${targetCenterX.toFixed(2)}, ${targetCenterY.toFixed(2)}) rotate(${rot}) scale(${finalScaleX.toFixed(4)}, ${finalScaleY.toFixed(4)}) translate(-100, -100)`;

        let innerContent = '';
        if (data.svg) {
          innerContent = extractInnerSvg(data.svg);
        } else {
          innerContent = `<text x="100" y="100" dominant-baseline="central" text-anchor="middle" font-size="145" font-family="'UserCustomFont', var(--font-serif)">${esc(data.char)}</text>`;
        }

        slotsSvgHtml += `
          <g id="legoGroup_${slotKey}" class="lego-slot-group" transform="${transformAttr}">
            ${innerContent}
          </g>
        `;
      });

      container.innerHTML = slotsSvgHtml;
      renderSlotIndicators();
    }

    // 渲染插槽外层矩形指示器
    function renderSlotIndicators() {
      const indContainer = document.getElementById('legoSlotIndicators');
      const effSlots = getEffectiveSlots();
      if (!indContainer) return;

      indContainer.innerHTML = Object.keys(effSlots).map(slotKey => {
        const slotDef = effSlots[slotKey];
        const isActive = slotKey === activeSlotKey;
        // 换算 200x200 viewBox 到百分比位置尺寸 (兼容移动端等任意画布尺寸)
        const left = (slotDef.x / 2).toFixed(2);
        const top = (slotDef.y / 2).toFixed(2);
        const w = (slotDef.w / 2).toFixed(2);
        const h = (slotDef.h / 2).toFixed(2);

        const data = legoSlotsData[slotKey] || {};
        const charBadge = data.char ? `· ${esc(data.char)}` : '';

        return `
          <div class="slot-rect-indicator ${isActive ? 'active' : ''}" 
               style="left:${left}%; top:${top}%; width:${w}%; height:${h}%;"
               onclick="selectActiveSlot('${slotKey}')">
            <span class="slot-pill-tag">${slotKey} ${charBadge}</span>
          </div>
        `;
      }).join('');
    }

    // 更新微调面板 UI 滑块值与细分下拉框
    function updateTransformPanelUI() {
      const effSlots = getEffectiveSlots();
      const slotDef = effSlots[activeSlotKey];
      const data = legoSlotsData[activeSlotKey] || {};

      const titleEl = document.getElementById('activeSlotTitle');
      if (titleEl) {
        const slotLabel = slotDef ? slotDef.label : activeSlotKey;
        titleEl.innerText = data.char 
          ? `插槽 ${activeSlotKey} (${slotLabel}): 部件【${data.char}】`
          : `插槽 ${activeSlotKey} (${slotLabel}): [未放入部件]`;
      }

      // 同步细分下拉框状态
      const subdivideSelect = document.getElementById('slotSubdivideSelect');
      if (subdivideSelect && slotDef) {
        const pKey = slotDef.parentKey || activeSlotKey;
        subdivideSelect.value = slotSubdivisions[pKey] || 'none';
      }

      document.getElementById('ctrlOffsetX').value = data.offsetX || 0;
      document.getElementById('valOffsetX').innerText = data.offsetX || 0;

      document.getElementById('ctrlOffsetY').value = data.offsetY || 0;
      document.getElementById('valOffsetY').innerText = data.offsetY || 0;

      document.getElementById('ctrlScaleX').value = data.scaleX || 1.0;
      document.getElementById('valScaleX').innerText = (data.scaleX || 1.0).toFixed(2);

      document.getElementById('ctrlScaleY').value = data.scaleY || 1.0;
      document.getElementById('valScaleY').innerText = (data.scaleY || 1.0).toFixed(2);

      document.getElementById('ctrlRotate').value = data.rotate || 0;
      document.getElementById('valRotate').innerText = data.rotate || 0;

      const flipBtn = document.getElementById('btnFlipX');
      if (flipBtn) {
        flipBtn.style.background = data.flipX ? 'var(--primary-light)' : '#faf8f5';
        flipBtn.style.color = data.flipX ? 'var(--primary)' : '#555';
        flipBtn.style.borderColor = data.flipX ? 'var(--primary)' : '#dcd3c5';
      }
    }

    // 滑块微调事件响应
    function updateSlotTransform() {
      const data = legoSlotsData[activeSlotKey];
      if (!data) return;

      data.offsetX = parseFloat(document.getElementById('ctrlOffsetX').value) || 0;
      document.getElementById('valOffsetX').innerText = data.offsetX;

      data.offsetY = parseFloat(document.getElementById('ctrlOffsetY').value) || 0;
      document.getElementById('valOffsetY').innerText = data.offsetY;

      data.scaleX = parseFloat(document.getElementById('ctrlScaleX').value) || 1.0;
      document.getElementById('valScaleX').innerText = data.scaleX.toFixed(2);

      data.scaleY = parseFloat(document.getElementById('ctrlScaleY').value) || 1.0;
      document.getElementById('valScaleY').innerText = data.scaleY.toFixed(2);

      data.rotate = parseInt(document.getElementById('ctrlRotate').value, 10) || 0;
      document.getElementById('valRotate').innerText = data.rotate;

      renderLegoCanvas();
    }

    function toggleFlipX() {
      const data = legoSlotsData[activeSlotKey];
      if (!data) return;
      data.flipX = !data.flipX;
      updateTransformPanelUI();
      renderLegoCanvas();
    }

    function resetSlotTransform() {
      const data = legoSlotsData[activeSlotKey];
      if (!data) return;
      data.offsetX = 0;
      data.offsetY = 0;
      data.scaleX = 1.0;
      data.scaleY = 1.0;
      data.rotate = 0;
      data.flipX = false;
      updateTransformPanelUI();
      renderLegoCanvas();
    }

    function clearCurrentSlot() {
      const data = legoSlotsData[activeSlotKey];
      if (!data) return;
      data.char = '';
      data.svg = '';
      resetSlotTransform();
      renderSlotTabs();
      updateTransformPanelUI();
      updateLegoIds();
    }

    function resetAllSlots() {
      applyLayoutSlots(currentLegoLayout, false);
      renderSlotTabs();
      renderLegoCanvas();
      updateTransformPanelUI();
      updateLegoIds();
      showToast('已清空当前画布所有部件');
    }

    // 动态生成 IDS 表达式（支持任意用户自由嵌套的间架骨架）
    function updateLegoIds() {
      const tpl = LEGO_LAYOUTS[currentLegoLayout];
      if (!tpl) return;

      function getSlotIdcFragment(key) {
        const sub = slotSubdivisions[key] || 'none';
        if (sub === 'left-right') {
          const c1 = legoSlotsData[`${key}1`]?.char || '？';
          const c2 = legoSlotsData[`${key}2`]?.char || '？';
          return `⿰${c1}${c2}`;
        } else if (sub === 'top-bottom') {
          const c1 = legoSlotsData[`${key}1`]?.char || '？';
          const c2 = legoSlotsData[`${key}2`]?.char || '？';
          return `⿱${c1}${c2}`;
        } else if (sub === 'left-mid-right') {
          const c1 = legoSlotsData[`${key}1`]?.char || '？';
          const c2 = legoSlotsData[`${key}2`]?.char || '？';
          const c3 = legoSlotsData[`${key}3`]?.char || '？';
          return `⿲${c1}${c2}${c3}`;
        } else if (sub === 'top-mid-bottom') {
          const c1 = legoSlotsData[`${key}1`]?.char || '？';
          const c2 = legoSlotsData[`${key}2`]?.char || '？';
          const c3 = legoSlotsData[`${key}3`]?.char || '？';
          return `⿳${c1}${c2}${c3}`;
        } else if (sub === 'triplet') {
          const c1 = legoSlotsData[`${key}1`]?.char || '？';
          const c2 = legoSlotsData[`${key}2`]?.char || '？';
          const c3 = legoSlotsData[`${key}3`]?.char || '？';
          return `⿱${c1}⿰${c2}${c3}`;
        } else if (sub === 'surround') {
          const c1 = legoSlotsData[`${key}1`]?.char || '？';
          const c2 = legoSlotsData[`${key}2`]?.char || '？';
          return `⿴${c1}${c2}`;
        } else if (sub === 'quad') {
          const c1 = legoSlotsData[`${key}1`]?.char || '？';
          const c2 = legoSlotsData[`${key}2`]?.char || '？';
          const c3 = legoSlotsData[`${key}3`]?.char || '？';
          const c4 = legoSlotsData[`${key}4`]?.char || '？';
          return `⿱⿰${c1}${c2}⿰${c3}${c4}`;
        } else {
          return legoSlotsData[key]?.char || '？';
        }
      }

      let ids = '';
      if (currentLegoLayout === 'left-right') {
        ids = `⿰${getSlotIdcFragment('A')}${getSlotIdcFragment('B')}`;
      } else if (currentLegoLayout === 'top-bottom') {
        ids = `⿱${getSlotIdcFragment('A')}${getSlotIdcFragment('B')}`;
      } else if (currentLegoLayout === 'left-mid-right') {
        ids = `⿲${getSlotIdcFragment('A')}${getSlotIdcFragment('B')}${getSlotIdcFragment('C')}`;
      } else if (currentLegoLayout === 'top-mid-bottom') {
        ids = `⿳${getSlotIdcFragment('A')}${getSlotIdcFragment('B')}${getSlotIdcFragment('C')}`;
      } else if (currentLegoLayout === 'surround') {
        ids = `⿴${getSlotIdcFragment('A')}${getSlotIdcFragment('B')}`;
      } else if (currentLegoLayout === 'triplet') {
        ids = `⿱${getSlotIdcFragment('A')}⿰${getSlotIdcFragment('B')}${getSlotIdcFragment('C')}`;
      } else if (currentLegoLayout === 'quad') {
        ids = `⿱⿰${getSlotIdcFragment('A')}${getSlotIdcFragment('B')}⿰${getSlotIdcFragment('C')}${getSlotIdcFragment('D')}`;
      } else {
        ids = `⿻${getSlotIdcFragment('A')}${getSlotIdcFragment('B')}`;
      }

      const idsInput = document.getElementById('legoIds');
      if (idsInput) idsInput.value = ids;
    }

    // 汉语拼音标调对照映射 (韵母 a, o, e, i, u, ü)
    const PINYIN_TONE_MAP = {
      a: ['ā', 'á', 'ǎ', 'à'],
      o: ['ō', 'ó', 'ǒ', 'ò'],
      e: ['ē', 'é', 'ě', 'è'],
      i: ['ī', 'í', 'ǐ', 'ì'],
      u: ['ū', 'ú', 'ǔ', 'ù'],
      v: ['ǖ', 'ǘ', 'ǚ', 'ǜ'],
      ü: ['ǖ', 'ǘ', 'ǚ', 'ǜ'],
    };

    // 智能汉语拼音数字转标调算法 (符合国家标准通用拼音标调规范)
    function convertPinyinTones(text) {
      if (!text) return '';
      return text.replace(/([a-zA-ZüÜvV]+)([1-5])/g, (match, word, toneStr) => {
        const tone = parseInt(toneStr, 10);
        if (tone < 1 || tone > 4) return word; // 5 为轻声
        const lower = word.toLowerCase();

        // 标调规则：
        // 1. 有 a 优先标 a
        let targetIdx = lower.indexOf('a');
        // 2. 没 a 找 o 或 e
        if (targetIdx === -1) targetIdx = lower.indexOf('o');
        if (targetIdx === -1) targetIdx = lower.indexOf('e');
        // 3. iu 或 ui 并排标在后
        if (targetIdx === -1) {
          if (lower.includes('iu')) targetIdx = lower.indexOf('u');
          else if (lower.includes('ui')) targetIdx = lower.indexOf('i');
          else if (lower.indexOf('i') !== -1) targetIdx = lower.indexOf('i');
          else if (lower.indexOf('u') !== -1) targetIdx = lower.indexOf('u');
          else if (lower.indexOf('v') !== -1) targetIdx = lower.indexOf('v');
          else if (lower.indexOf('ü') !== -1) targetIdx = lower.indexOf('ü');
        }

        if (targetIdx !== -1) {
          const char = lower[targetIdx];
          const toneChar = (PINYIN_TONE_MAP[char] || [])[tone - 1];
          if (toneChar) {
            const isUpper = word[targetIdx] === word[targetIdx].toUpperCase() && word[targetIdx] !== word[targetIdx].toLowerCase();
            const finalChar = isUpper ? toneChar.toUpperCase() : toneChar;
            return word.slice(0, targetIdx) + finalChar + word.slice(targetIdx + 1);
          }
        }
        return word;
      });
    }

    // 监听拼音输入框实时自动转换声调
    function handlePinyinInput(inputEl) {
      if (!inputEl) return;
      const start = inputEl.selectionStart;
      const end = inputEl.selectionEnd;
      const original = inputEl.value;
      const converted = convertPinyinTones(original);
      if (converted !== original) {
        inputEl.value = converted;
        const diff = converted.length - original.length;
        try {
          inputEl.setSelectionRange(start + diff, end + diff);
        } catch (e) {}
      }
    }

    // 展开/收起 24 声调字符浮窗
    function togglePinyinKeyboard(e) {
      if (e) e.stopPropagation();
      const popover = document.getElementById('pinyinKbPopover');
      if (popover) {
        popover.classList.toggle('open');
      }
    }

    // 点击浮窗声调字符追加到输入框光标处
    function appendPinyinChar(char) {
      const input = document.getElementById('legoPinyin');
      if (!input) return;
      const start = input.selectionStart != null ? input.selectionStart : input.value.length;
      const end = input.selectionEnd != null ? input.selectionEnd : input.value.length;
      const val = input.value || '';
      input.value = val.substring(0, start) + char + val.substring(end);
      input.focus();
      try {
        input.setSelectionRange(start + char.length, start + char.length);
      } catch (e) {}
    }

    // 点击页面任意外部区域收起拼音声调小浮窗
    document.addEventListener('click', (e) => {
      const popover = document.getElementById('pinyinKbPopover');
      if (popover && popover.classList.contains('open')) {
        if (!popover.contains(e.target) && !e.target.closest('.pinyin-toggle-btn')) {
          popover.classList.remove('open');
        }
      }
    });

    // 核心：生成标准的纯净独立 SVG 矢量代码
    function generateCleanSvgString() {
      const container = document.getElementById('legoSlotsContainer');
      const innerSvg = container ? container.innerHTML : '';
      return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="400" height="400">
  <g fill="#1a1a1a">
    ${innerSvg}
  </g>
</svg>`;
    }

    // 1. 导出独立矢量 SVG
    function exportLegoSvg() {
      const pinyin = (document.getElementById('legoPinyin').value || '').trim() || 'custom';
      const ids = (document.getElementById('legoIds').value || '').trim();
      const svgStr = generateCleanSvgString();

      const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `新造字_${pinyin}_${ids}.svg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('已导出标准矢量 SVG 文件！');
    }

    // 2. 导出高清 PNG 图 (800x800 透明底)
    function exportLegoPng() {
      const pinyin = (document.getElementById('legoPinyin').value || '').trim() || 'custom';
      const svgStr = generateCleanSvgString();
      const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);

      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = 800;
        canvas.height = 800;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, 800, 800);
        ctx.drawImage(img, 0, 0, 800, 800);

        canvas.toBlob(pngBlob => {
          const pngUrl = URL.createObjectURL(pngBlob);
          const a = document.createElement('a');
          a.href = pngUrl;
          a.download = `新造字_${pinyin}.png`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(pngUrl);
          URL.revokeObjectURL(url);
          showToast('已导出高清透明 PNG 图片！');
        }, 'image/png');
      };
      img.src = url;
    }

    // 3. 生成宣纸造字档案卡
    function generateLegoCard() {
      const pinyin = (document.getElementById('legoPinyin').value || '').trim() || 'wú';
      const ids = document.getElementById('legoIds').value;
      const liushu = document.getElementById('legoLiushu').value;
      const meaning = (document.getElementById('legoMeaning').value || '').trim() || '此字聚万物之气韵，承天意而幻化，妙手偶得之。';
      const author = (document.getElementById('legoAuthor').value || '').trim() || '造字人 敬造';

      document.getElementById('cardPinyin').innerText = pinyin;
      document.getElementById('cardIds').innerText = ids;
      document.getElementById('cardLiushu').innerText = liushu;
      document.getElementById('cardMeaning').innerText = meaning;
      document.getElementById('cardAuthor').innerText = author;

      // 日期自动换算农历甲辰风味
      const now = new Date();
      const yearStr = `${now.getFullYear()}年${now.getMonth() + 1}月`;
      document.getElementById('cardDate').innerText = yearStr;

      // 注入 SVG 矢量
      const svgBox = document.getElementById('cardMizigeBox');
      svgBox.innerHTML = `
        <svg viewBox="0 0 200 200" width="100%" height="100%">
          <g fill="#1a1a1a">
            ${document.getElementById('legoSlotsContainer').innerHTML}
          </g>
        </svg>
      `;

      document.getElementById('legoCardModal').style.display = 'flex';
    }

    function closeCardModal() {
      document.getElementById('legoCardModal').style.display = 'none';
    }

    // 下载古典造字卡图片 (Canvas 高清渲染)
    function downloadLegoCardImage() {
      const cardArea = document.getElementById('legoCardExportArea');
      const pinyin = document.getElementById('cardPinyin').innerText;
      const ids = document.getElementById('cardIds').innerText;
      const liushu = document.getElementById('cardLiushu').innerText;
      const meaning = document.getElementById('cardMeaning').innerText;
      const author = document.getElementById('cardAuthor').innerText;
      const dateStr = document.getElementById('cardDate').innerText;

      const svgStr = generateCleanSvgString();
      const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const svgUrl = URL.createObjectURL(svgBlob);

      const glyphImg = new Image();
      glyphImg.onload = () => {
        const W = 900;
        const H = 1260;
        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');

        // 1. 宣纸底色
        ctx.fillStyle = '#faf5ea';
        ctx.fillRect(0, 0, W, H);

        // 2. 双层古典红边框与边饰
        ctx.lineWidth = 14;
        ctx.strokeStyle = '#c2a688';
        ctx.strokeRect(16, 16, W - 32, H - 32);

        ctx.lineWidth = 4;
        ctx.strokeStyle = '#b83b26';
        ctx.strokeRect(48, 48, W - 96, H - 96);

        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(184, 59, 38, 0.4)';
        ctx.strokeRect(56, 56, W - 112, H - 112);

        // 3. 顶部标题与印章
        ctx.font = 'bold 36px "Songti SC", "SimSun", serif';
        ctx.fillStyle = '#2c3e50';
        ctx.textAlign = 'left';
        ctx.fillText('新 造 字 譜', 90, 130);

        // 朱砂印章
        ctx.fillStyle = '#b83b26';
        ctx.fillRect(W - 150, 88, 54, 54);
        ctx.font = 'bold 32px "Songti SC", "SimSun", serif';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.fillText('造', W - 123, 126);

        // 4. 核心米字格底图
        const mzSize = 420;
        const mzX = (W - mzSize) / 2;
        const mzY = 180;

        ctx.fillStyle = '#fdfaf4';
        ctx.fillRect(mzX, mzY, mzSize, mzSize);
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#d4a373';
        ctx.strokeRect(mzX, mzY, mzSize, mzSize);

        // 米字格辅线
        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(184, 59, 38, 0.25)';
        ctx.beginPath();
        ctx.moveTo(mzX + mzSize / 2, mzY); ctx.lineTo(mzX + mzSize / 2, mzY + mzSize);
        ctx.moveTo(mzX, mzY + mzSize / 2); ctx.lineTo(mzX + mzSize, mzY + mzSize / 2);
        ctx.moveTo(mzX, mzY); ctx.lineTo(mzX + mzSize, mzY + mzSize);
        ctx.moveTo(mzX + mzSize, mzY); ctx.lineTo(mzX, mzY + mzSize);
        ctx.stroke();

        // 绘制矢量字形
        const glyphPad = 36;
        ctx.drawImage(glyphImg, mzX + glyphPad, mzY + glyphPad, mzSize - glyphPad * 2, mzSize - glyphPad * 2);

        // 5. 拼音、结构与六书标签
        ctx.font = 'bold 34px -apple-system, sans-serif';
        ctx.fillStyle = '#b83b26';
        ctx.textAlign = 'center';
        ctx.fillText(pinyin, W / 2, 660);

        ctx.font = '24px "Songti SC", "SimSun", serif';
        ctx.fillStyle = '#666';
        ctx.fillText(`结构: ${ids}   |   归类: ${liushu}`, W / 2, 706);

        // 分隔红线
        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(184, 59, 38, 0.3)';
        ctx.beginPath();
        ctx.moveTo(120, 740);
        ctx.lineTo(W - 120, 740);
        ctx.stroke();

        // 6. 字义典故与说明 (自动折行排版)
        ctx.font = '24px "Songti SC", "SimSun", serif';
        ctx.fillStyle = '#3a322c';
        ctx.textAlign = 'left';

        const maxTextWidth = W - 240;
        let line = '';
        let startY = 800;
        const lineHeight = 44;

        for (let i = 0; i < meaning.length; i++) {
          const testLine = line + meaning[i];
          const metrics = ctx.measureText(testLine);
          if (metrics.width > maxTextWidth && i > 0) {
            ctx.fillText(line, 120, startY);
            line = meaning[i];
            startY += lineHeight;
          } else {
            line = testLine;
          }
        }
        ctx.fillText(line, 120, startY);

        // 7. 底部落款与署名
        ctx.font = '20px "Songti SC", "SimSun", serif';
        ctx.fillStyle = '#8c7b70';
        ctx.textAlign = 'left';
        ctx.fillText(author, 120, H - 90);
        ctx.textAlign = 'right';
        ctx.fillText(dateStr, W - 120, H - 90);

        // 导出并下载
        canvas.toBlob(blob => {
          const downloadUrl = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = downloadUrl;
          a.download = `新造字譜_${pinyin}.png`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(downloadUrl);
          URL.revokeObjectURL(svgUrl);
          showToast('已保存宣纸造字档案卡图片！');
        }, 'image/png');
      };
      glyphImg.src = svgUrl;
    }

    // 4. 收录至我的自造字库 (Local Storage)
    function saveToPersonalVault() {
      const pinyin = (document.getElementById('legoPinyin').value || '').trim() || 'wú';
      const ids = document.getElementById('legoIds').value;
      const liushu = document.getElementById('legoLiushu').value;
      const meaning = (document.getElementById('legoMeaning').value || '').trim();
      const author = (document.getElementById('legoAuthor').value || '').trim();

      const item = {
        id: 'lego_' + Date.now(),
        layout: currentLegoLayout,
        subdivisions: JSON.parse(JSON.stringify(slotSubdivisions)),
        slots: JSON.parse(JSON.stringify(legoSlotsData)),
        svgData: generateCleanSvgString(),
        pinyin: pinyin,
        ids: ids,
        liushu: liushu,
        meaning: meaning,
        author: author,
        createdAt: new Date().toLocaleDateString()
      };

      let vault = [];
      try {
        vault = JSON.parse(localStorage.getItem('hanzi_lego_vault') || '[]');
      } catch (e) {
        vault = [];
      }

      vault.unshift(item);
      localStorage.setItem('hanzi_lego_vault', JSON.stringify(vault));

      updateVaultBadge();
      showToast(`已收入我的自造字库！主站搜索【${pinyin}】或【${ids}】即可找到！`);
    }

    function updateVaultBadge() {
      try {
        const vault = JSON.parse(localStorage.getItem('hanzi_lego_vault') || '[]');
        const badge = document.getElementById('vaultCount');
        if (badge) badge.innerText = vault.length;
      } catch (e) {}
    }

    function toggleLegoVault() {
      const drawer = document.getElementById('legoVaultDrawer');
      if (!drawer) return;
      drawer.classList.toggle('open');
      if (drawer.classList.contains('open')) {
        renderLegoVault();
      }
    }

    function renderLegoVault() {
      const container = document.getElementById('legoVaultList');
      if (!container) return;
      let vault = [];
      try {
        vault = JSON.parse(localStorage.getItem('hanzi_lego_vault') || '[]');
      } catch (e) {
        vault = [];
      }

      if (vault.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:#999; padding:40px 10px;">宝库尚空，造个新字存进来吧！</div>';
        return;
      }

      container.innerHTML = vault.map(v => {
        return `
          <div class="vault-card" id="vc_${v.id}">
            <div class="vault-glyph-preview">
              ${v.svgData}
            </div>
            <div class="vault-info">
              <div class="vault-title-row">
                <span class="vault-name">${esc(v.ids)}</span>
                <span class="vault-pinyin">${esc(v.pinyin)}</span>
              </div>
              <div class="vault-desc" title="${esc(v.meaning)}">${esc(v.meaning || '无释义')}</div>
            </div>
            <div class="vault-actions">
              <button class="vault-btn" onclick="loadVaultItem('${v.id}')" title="载入继续编辑">✏️</button>
              <button class="vault-btn" onclick="deleteVaultItem('${v.id}')" title="删除">🗑️</button>
            </div>
          </div>
        `;
      }).join('');
    }

    function loadVaultItem(id) {
      let vault = JSON.parse(localStorage.getItem('hanzi_lego_vault') || '[]');
      const item = vault.find(x => x.id === id);
      if (!item) return;

      currentLegoLayout = item.layout || 'left-right';
      slotSubdivisions = item.subdivisions ? JSON.parse(JSON.stringify(item.subdivisions)) : {};
      legoSlotsData = item.slots || {};
      document.getElementById('legoPinyin').value = item.pinyin || '';
      document.getElementById('legoLiushu').value = item.liushu || '会意字';
      document.getElementById('legoMeaning').value = item.meaning || '';
      document.getElementById('legoAuthor').value = item.author || '造字人 敬造';

      document.querySelectorAll('#legoTemplatesBar .lego-tpl-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.layout === currentLegoLayout);
      });

      renderSlotTabs();
      renderLegoCanvas();
      updateTransformPanelUI();
      updateLegoIds();
      const drawer = document.getElementById('legoVaultDrawer');
      if (drawer) drawer.classList.remove('open');
      showToast('已重新载入自造字档案！');
    }

    function deleteVaultItem(id) {
      let vault = JSON.parse(localStorage.getItem('hanzi_lego_vault') || '[]');
      vault = vault.filter(x => x.id !== id);
      localStorage.setItem('hanzi_lego_vault', JSON.stringify(vault));
      updateVaultBadge();
      renderLegoVault();
      showToast('已从自造字库中移除');
    }

    // 汉字乐高初始化与 URL 参数监听
    function initLegoApp() {
      updateVaultBadge();
      initLegoStudio();

      // 解析 URL 参数以实现跨页面互联引用 (例如 /lego?load=lego_12345 或 /lego?char=赢)
      const urlParams = new URLSearchParams(window.location.search);
      const loadId = urlParams.get('load');
      const charParam = urlParams.get('char');

      if (loadId) {
        setTimeout(() => {
          loadVaultItem(loadId);
        }, 150);
      } else if (charParam) {
        setTimeout(() => {
          const charInput = document.getElementById('legoCharInput');
          if (charInput) {
            charInput.value = charParam;
            disassembleInputChar();
          }
        }, 150);
      }
    }

    // ESC 关闭档案卡弹窗或造字库抽屉
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const cardModal = document.getElementById('legoCardModal');
        if (cardModal && cardModal.style.display === 'flex') {
          closeCardModal();
          return;
        }
        const drawer = document.getElementById('legoVaultDrawer');
        if (drawer && drawer.classList.contains('open')) {
          toggleLegoVault();
          return;
        }
      }
    });

    // 移动端分段快捷平滑滚动
    window.scrollToLegoSection = function(sec) {
      const map = {
        stage: '#legoArtboard',
        bricks: '#legoSidebarLeft',
        controls: '#legoTransformPanel',
        export: '#legoSidebarRight'
      };
      const selector = map[sec];
      if (!selector) return;
      const el = document.querySelector(selector);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        document.querySelectorAll('.lego-mobile-nav-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.querySelector(`.lego-mobile-nav-btn[data-sec="${sec}"]`);
        if (activeBtn) activeBtn.classList.add('active');
      }
    };

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initLegoApp);
    } else {
      initLegoApp();
    }
