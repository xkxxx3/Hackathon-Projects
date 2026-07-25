/* ============ 玩点真的 Demo · 逻辑层 ============ */
const S = {
  entry: 'organic',      // 'douyin' = 玩同款入口 | 'organic' = 主动打开
  mode: 'light',         // 'light' 空档来一局 | 'full' 聚会开个局
  relation: '半熟朋友',
  suits: ['sp'],         // 已选花色
  minutes: 3,
  players: 6,
  recording: false,
  evMark: null,
  chosen: null,
  eventFired: false,
  roundSec: 90,
  objects: [
    { id:'cups',    name:'纸杯',   count:6, emoji:'🥤', on:true },
    { id:'chops',   name:'筷子',   count:8, emoji:'🥢', on:true },
    { id:'napkins', name:'餐巾纸', count:1, emoji:'🧻', on:true },
    { id:'coaster', name:'杯垫',   count:4, emoji:'🟤', on:true },
    { id:'menu',    name:'菜单',   count:2, emoji:'📋', on:false },
  ],
};

const SUIT_META = {
  sp: { icon:'♠', name:'活力局', cls:'su-sp', tag:'gt-sp' },
  di: { icon:'♦', name:'脑洞局', cls:'su-di', tag:'gt-pp' },
  cl: { icon:'♣', name:'合作局', cls:'su-cl', tag:'gt-bl' },
  he: { icon:'♥', name:'默契局', cls:'su-he', tag:'gt-yl' },
};

/* ============ TTS ============ */
function speak(text, cb){
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'zh-CN'; u.rate = 1.05;
    u.onend = () => { setSpeaking(false); cb && cb(); };
    u.onerror = () => { setSpeaking(false); cb && cb(); };
    setSpeaking(true);
    speechSynthesis.speak(u);
  } catch(e){ cb && cb(); }
}
function setSpeaking(on){
  const el = document.getElementById('speaking');
  if (el) el.textContent = on ? '🔊 AI 主持人正在讲话…' : '';
}

/* ============ 生成引擎：机制库先验 × 已确认物件 × 花色 × 人数 ============ */
function genVariants(){
  const has = id => { const o = S.objects.find(o=>o.id===id); return o && o.on; };
  const cnt = id => { const o = S.objects.find(o=>o.id===id); return o ? o.count : 0; };
  const n = S.players;
  const pool = [];

  // ♠ 活力局
  if (has('napkins')) pool.push({
    suit:'sp', name:'纸团别落桌', skeleton:'接力 · 同步',
    hook:`这局要用桌上的餐巾纸玩不落桌接力！`,
    desc:`${n} 人分两组隔位坐开，揉一个纸团用手掌拍击保持在空中，按座位顺序传给队友；落桌由失误者重新发起。90 秒内传递轮数多的组赢。`,
    rules:[`${n} 人分两组，隔位坐开`,`揉一个餐巾纸团`,`手掌拍击传给下一位队友`,`落桌者重新发起`,`90 秒传递轮数多者胜`],
    speech:`规则很简单。${n}个人分成两组，隔位坐开。把餐巾纸揉成一个纸团，用手掌拍击让它不落桌，按座位顺序传给你的队友。掉在桌上，由失误的人重新发起。90秒倒计时，传递轮数多的组获胜。准备好了吗？`
  });
  if (has('cups')) pool.push({
    suit:'sp', name:'吹杯过桌', skeleton:'限时挑战',
    hook:`这局要把纸杯从桌这头吹到那头！`,
    desc:`两组各一个倒扣纸杯，只能用嘴吹动横穿桌面，出界拉回起点。先到对岸的组赢，两轮定胜负。`,
    rules:[`纸杯倒扣在桌沿`,`只能用嘴吹`,`出界回起点`,`先到对岸者胜`,`两轮定胜负`],
    speech:`两组各一个倒扣的纸杯放在桌沿，只能用嘴吹，让它横穿桌面到对岸。吹出界拉回起点重来。先到对岸的组赢，两轮定胜负。准备好了吗？`
  });

  // ♦ 脑洞局
  if (has('menu')) pool.push({
    suit:'di', name:'菜单盲猜', skeleton:'猜测 · 信息差',
    hook:`这局要用菜单玩盲猜价格！`,
    desc:`轮流指一道菜遮住价格，其他人竞猜，最接近者得 1 分。5 轮总分高者赢。`,
    rules:[`轮流出题遮价格`,`其他人同时报数`,`最接近得 1 分`,`5 轮定胜负`],
    speech:`轮流从菜单里指一道菜，遮住价格，其他人同时猜价，最接近的得一分。五轮总分最高的人获胜。准备好了吗？`
  });
  if (has('coaster')) pool.push({
    suit:'di', name:'杯垫记忆翻牌', skeleton:'记忆 · 观察',
    hook:`这局要用 ${cnt('coaster')} 个杯垫玩记忆挑战！`,
    desc:`杯垫下藏不同小物（筷套、糖包等），所有人看 5 秒后打乱。轮流指认"哪个杯垫下是什么"，答错淘汰，最后留下的人赢。`,
    rules:[`杯垫下各藏一件小物`,`全员看 5 秒`,`打乱位置`,`轮流指认`,`答错出局，剩者为王`],
    speech:`在每个杯垫下面藏一件小东西，所有人看5秒，然后打乱位置。轮流指认哪个杯垫下面是什么，答错的出局，坚持到最后的人获胜。准备好了吗？`
  });

  // ♣ 合作局
  if (has('cups') && has('chops')) pool.push({
    suit:'cl', name:'共筑杯塔', skeleton:'联合建造 · 同步',
    hook:`这局全桌是一队——${cnt('cups')} 个纸杯共筑一塔！`,
    desc:`全员一队，每人每次只能用一根筷子操作，轮流把纸杯叠成塔。塔倒全队重来。90 秒内塔高超过 3 层算全队获胜。`,
    rules:[`全员同队`,`每人一根筷子`,`轮流叠杯，手不能碰杯`,`塔倒重来`,`90 秒 3 层达标`],
    speech:`这局大家是一个队。每人拿一根筷子，轮流把纸杯叠成塔，手不能碰杯子。塔倒了全队重来。90秒之内叠到三层，就是全队的胜利。准备好了吗？`
  });

  // ♥ 默契局
  pool.push({
    suit:'he', name:'无声同频', skeleton:'默契 · 预测',
    hook:`这局不许说话——考验你们的默契！`,
    desc:`每轮主持人出一个题（如"桌上最好吃的菜"），所有人同时用手指向自己的答案，指向最集中的答案的人得分。5 轮后分高者是"本桌最懂大家的人"。`,
    rules:[`全程不许说话`,`听题后同时用手指`,`指向最多者得分`,`5 轮定榜首`],
    speech:`这局全程不许说话。每轮我出一个题，比如桌上最好吃的菜，所有人同时用手指向自己的答案。和大多数人指向一致的得分。五轮之后，分最高的就是本桌最懂大家的人。准备好了吗？`
  });

  // 花色过滤：优先已选花色，不足 3 个则放开补齐
  const picked = pool.filter(v => S.suits.includes(v.suit));
  const rest = pool.filter(v => !S.suits.includes(v.suit));
  return picked.concat(rest).slice(0, 3);
}

const EVENTS = [
  '全体改用非惯用手！',
  '顺序反转！从最后一位重新开始！',
  '接下来 15 秒，动作放慢一倍！',
  '当前领先的组，下一棒闭一只眼！',
];

/* ============ 屏幕渲染 ============ */
const app = document.getElementById('app');

/* 屏 A：抖音模拟页（玩同款入口） */
function screenDouyin(){
  S.entry = 'douyin';
  app.innerHTML = `
  <div class="screen"><div class="dy">
    <div class="dy-video">
      <div class="emoji">🎈</div>
      <div style="font-size:17px;font-weight:700;color:#fff">气球不落地接力挑战</div>
      <div style="font-size:12px;opacity:.6;color:#fff">全场笑声一个接一个</div>
    </div>
    <div class="dy-play">▶</div>
    <div class="dy-hint">模拟抖音视频页 ·「玩同款」为平台挂载胶囊（同「画圈搜索」交互位），Demo 中模拟</div>
    <span class="dy-tag" onclick="tagJump()">🎮 玩同款 <span class="arr">›</span></span>
    <div class="dy-side">
      <div class="it"><span class="ic">❤️</span>2293</div>
      <div class="it"><span class="ic">💬</span>17</div>
      <div class="it"><span class="ic">⭐</span>2050</div>
      <div class="it"><span class="ic">↗️</span>1555</div>
    </div>
    <div class="dy-meta">
      <div class="author">@聚会玩法收集舍 · 03月24日</div>
      六个人快笑疯了哈哈哈哈，氛围直接拉满 #聚会游戏 #接力挑战
    </div>
  </div></div>`;
}
function tagJump(){
  app.innerHTML = `
  <div class="screen"><div class="loading">
    <div class="spinner"></div>
    <div>正在跳转小程序…</div>
    <div style="font-size:12px;color:#5a5a66">视频 ID 已带入 · 后端提取玩法骨架：接力 × 分组对抗</div>
  </div></div>`;
  setTimeout(screenSameLanding, 1400);
}

/* 屏 A2：同款落地页 */
function screenSameLanding(){
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">玩点真的</span><span>来自「玩同款」</span></div>
    <div class="hero">刷到的<span class="hl">同款</span>，<br>现在就能玩！</div>
    <p class="sub">AI 已提取「气球不落地接力」的玩法骨架：接力传递 × 分组竞速 × 东西不能掉。</p>
    <button class="bigbtn bb-yl" onclick="S.mode='light';screenSetup()">
      <span class="ic">⚡</span>
      <span><span class="t">同款立即开玩</span><span class="d" style="display:block">拍下现场，AI 保留骨架换道具</span></span>
      <span class="go">›</span>
    </button>
    <button class="bigbtn bb-pp" onclick="collectCase()">
      <span class="ic">⭐</span>
      <span><span class="t">先收藏</span><span class="d" style="display:block">等菜 / 等车的时候再玩</span></span>
      <span class="go">›</span>
    </button>
    <p class="hint">刷到时往往不方便玩——收藏后，空档时打开小程序随时开局</p>
  </div>`;
}
function collectCase(){
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = '✅ 已收藏，空档时见';
  document.getElementById('phone').appendChild(t);
  setTimeout(()=>{ t.remove(); screenHome(); }, 1200);
}

/* 屏 1：小程序首页（双模式 + 同款回流入口） */
function screenHome(){
  S.entry = 'organic';
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">一拍成局</span><span>⚙️</span></div>
    <div class="hero">人在一起，<br><span class="hl">就别只看手机</span></div>
    <p class="sub">拍一下现场，AI 马上给大家造个游戏。</p>
    <button class="bigbtn bb-yl" onclick="S.mode='light';screenSetup()">
      <span class="ic">🔥</span>
      <span><span class="t">空档来一局</span><span class="d" style="display:block">等上菜 · 排队 · 1—5 分钟</span></span>
      <span class="go">›</span>
    </button>
    <button class="bigbtn bb-pp" onclick="S.mode='full';screenSetup()">
      <span class="ic">👥</span>
      <span><span class="t">聚会开个局</span><span class="d" style="display:block">破冰 · 热场 · 5—20 分钟</span></span>
      <span class="go">›</span>
    </button>
    <div class="same-entry" onclick="screenCollected()">
      <span style="font-size:20px">📺</span>
      <span><span class="q" style="display:block">刷到一个好玩的？</span><span class="b">玩视频同款</span></span>
      <span class="arr">→</span>
    </div>
    <p class="hint">Demo 提示：从抖音「玩同款」进入的链路，点右上 ⚙️ 可重看</p>
  </div>`;
  // ⚙️ 彩蛋：回到抖音入口
  app.querySelector('.topbar span:last-child').onclick = screenDouyin;
  app.querySelector('.topbar span:last-child').style.cursor = 'pointer';
}

/* 收藏夹（主动入口的同款路径） */
function screenCollected(){
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">我的收藏</span><span onclick="screenHome()" style="cursor:pointer">‹ 返回</span></div>
    <div class="qtitle">收藏的玩法（1）</div>
    <div class="gamecard pickable" onclick="S.mode='light';screenSetup()">
      <span class="gc-badge">来自抖音</span>
      <div class="gc-name">🎈 气球不落地接力</div>
      <div class="gc-desc">骨架已提取：接力传递 × 分组竞速 × 东西不能掉。拍下你的现场，AI 把它改造成此时此地的版本。</div>
      <div class="gc-tags"><span class="gc-tag gt-sp">♠ 活力</span><span class="gc-tag gt-gray">原视频需要：气球×场地</span></div>
    </div>
    <button class="cta ghost" onclick="screenHome()">没想玩的？直接拍现场生成 →</button>
  </div>`;
}

/* 屏 2：局设置（关系 + 花色 + 时长） */
function screenSetup(){
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">${S.mode==='light'?'空档来一局':'聚会开个局'}</span><span onclick="screenHome()" style="cursor:pointer">‹</span></div>
    <div class="qtitle">你们是什么局？</div>
    <div class="rel-row" id="relRow">
      ${['刚认识','半熟朋友','熟人好友','老友重聚'].map(r=>`
        <div class="rel ${S.relation===r?'on':''}" onclick="setRel('${r}')"><span class="em">👥</span>${r}</div>`).join('')}
    </div>
    <div class="qtitle">这局想玩哪一类？</div>
    <div class="suits">
      ${Object.entries(SUIT_META).map(([k,m])=>`
        <div class="suit ${m.cls} ${S.suits.includes(k)?'on':''}" onclick="toggleSuit('${k}')">
          <div class="s">${m.icon} ${m.name}</div>
          <div class="m">${{sp:'反应 · 动作 · 竞速',di:'观察 · 记忆 · 推理',cl:'全员一队 · 共同目标',he:'预测 · 默契 · 心理'}[k]}</div>
        </div>`).join('')}
    </div>
    <div class="chips">
      ${[3,5,10].map(m=>`<button class="chip ${S.minutes===m?'on':''}" onclick="setMin(${m})">${m} 分钟</button>`).join('')}
    </div>
    <button class="cta" onclick="screenScan()">去看看现场 📷</button>
  </div>`;
}
function setRel(r){ S.relation = r; screenSetup(); }
function toggleSuit(k){
  const i = S.suits.indexOf(k);
  if (i >= 0) { if (S.suits.length > 1) S.suits.splice(i,1); }
  else S.suits.push(k);
  screenSetup();
}
function setMin(m){ S.minutes = m; screenSetup(); }

/* 屏 3：让 AI 看看现场（扫描动画 → 物件标签浮现） */
function screenScan(){
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">让 AI 看看现场</span><span onclick="screenSetup()" style="cursor:pointer">‹</span></div>
    <div class="scanbox" id="scanbox">
      <div class="corner c1"></div><div class="corner c2"></div><div class="corner c3"></div><div class="corner c4"></div>
      <div class="ph"><span class="em">📷</span>正在识别桌面物件与可动区域…</div>
    </div>
    <p class="hint">也可以手动告诉 AI 现场有什么</p>
  </div>`;
  // 物件标签逐个浮现
  const tags = [
    { txt:'🥤 纸杯 ×6', top:'18%', left:'12%' },
    { txt:'🥢 筷子',     top:'40%', left:'62%' },
    { txt:'🧻 餐巾纸',   top:'62%', left:'20%' },
    { txt:'⬜ 可活动区域·桌面', top:'80%', left:'34%' },
  ];
  tags.forEach((t,i)=>{
    setTimeout(()=>{
      const box = document.getElementById('scanbox');
      if (!box) return;
      const el = document.createElement('div');
      el.className = 'objtag';
      el.style.top = t.top; el.style.left = t.left;
      el.textContent = t.txt;
      box.appendChild(el);
    }, 500 + i*450);
  });
  setTimeout(screenConfirm, 500 + tags.length*450 + 700);
}

/* 屏 3b：确认现场条件 */
function screenConfirm(){
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">确认现场条件</span><span>只有确认的才进规则</span></div>
    <div class="panel" id="objlist">
      ${S.objects.map((o,i)=>`
        <div class="obj">
          <label><input type="checkbox" ${o.on?'checked':''} onchange="S.objects[${i}].on=this.checked">
          <span>${o.emoji} ${o.name}</span></label>
          <span class="cnt">× ${o.count}</span>
        </div>`).join('')}
    </div>
    <div class="panel">
      <div style="text-align:center;font-size:13px;color:var(--tx2);margin-bottom:4px">几个人玩？</div>
      <div class="players">
        <button onclick="chgPlayers(-1)">−</button>
        <div class="num" id="pnum">${S.players}</div>
        <button onclick="chgPlayers(1)">＋</button>
      </div>
    </div>
    <button class="cta" onclick="screenGenerating()">生成这局游戏 ⚡</button>
    <p class="hint">场景：餐厅桌面 → 自动只出桌面可完成的玩法（无跑动、无投掷）</p>
  </div>`;
}
function chgPlayers(d){
  S.players = Math.min(10, Math.max(2, S.players + d));
  document.getElementById('pnum').textContent = S.players;
}

/* 屏 4：生成中 → 局卡秒选 */
function screenGenerating(){
  const fromDy = S.entry === 'douyin';
  app.innerHTML = `
  <div class="screen"><div class="loading">
    <div class="spinner"></div>
    <div>${fromDy ? '正在把「气球接力」改造成你这桌的版本…' : '正在为你这桌造一局新游戏…'}</div>
    <div style="font-size:12px;color:#5a5a66">${fromDy ? '保留骨架 · 替换道具 · 绑定现场 · 加入意外' : '机制库选型 · 绑定现场 · 加入意外'}</div>
  </div></div>`;
  setTimeout(screenVariants, 1800);
}

function screenVariants(){
  const vs = genVariants();
  if (!vs.length) { alert('至少勾选一个物件'); return screenConfirm(); }
  window.__variants = vs;
  const fromDy = S.entry === 'douyin';
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">AI 已生成 ${vs.length} 局</span><span>组织者秒选</span></div>
    <p class="sub" style="margin-bottom:12px">${fromDy ? '都保留了原视频的接力竞速内核，但只在你这桌这么玩：' : '都来自验证过的机制库，绑定了你这桌的东西：'}</p>
    ${vs.map((v,i)=>{
      const m = SUIT_META[v.suit];
      return `
      <div class="gamecard pickable" onclick="pickVariant(${i})">
        <div class="gc-name">${v.name}</div>
        <div class="gc-desc">${v.desc}</div>
        <div class="gc-tags">
          <span class="gc-tag ${m.tag}">${m.icon} ${m.name}</span>
          <span class="gc-tag gt-gray">${v.skeleton}</span>
          <span class="gc-tag gt-gray">${S.players} 人 · ${S.minutes} 分钟</span>
        </div>
      </div>`;}).join('')}
  </div>`;
}
function pickVariant(i){ S.chosen = window.__variants[i]; screenRecAsk(); }

/* 屏 4b：开局前录制授权 */
function screenRecAsk(){
  screenHost();
  const mask = document.createElement('div');
  mask.className = 'mask'; mask.id = 'recMask';
  mask.innerHTML = `
    <div class="modal">
      <h3>📹 要不要顺便录下这局？</h3>
      <p>手机就立在桌上，AI 会在游戏进行时录制，结束后自动剪出 30 秒精彩片段。</p>
      <p style="font-size:12px;color:#5a5a66">· 默认不录，你主动开启才录<br>· 开启后 AI 会语音告知全桌"本局将录制"<br>· 成片先给你预览，发不发、发到哪，都由你决定</p>
      <button class="cta" onclick="setRec(true)">开启录制</button>
      <button class="cta ghost" onclick="setRec(false)">这局不录</button>
    </div>`;
  document.getElementById('phone').appendChild(mask);
}
function setRec(on){
  S.recording = on;
  document.getElementById('recMask').remove();
  if (on) {
    const bar = document.getElementById('recBar');
    if (bar) bar.style.display = 'block';
    speak('本局将录制精彩画面，介意的朋友现在可以说哦。');
  }
}

/* 屏 5：AI 主持台 */
let timerId = null;
function screenHost(){
  const v = S.chosen;
  S.eventFired = false;
  app.innerHTML = `
  <div class="screen"><div class="host">
    <div class="statebar">
      <div class="state on" id="st0">规则说明</div>
      <div class="state" id="st1">进行中</div>
      <div class="state" id="st2">随机事件</div>
      <div class="state" id="st3">结算</div>
    </div>
    <div class="hook">${v.hook}</div>
    <div class="recbar" id="recBar"><span class="rec-dot"></span>录制中 · 结束后自动剪 30 秒精彩片段</div>
    <div class="speaking" id="speaking"></div>
    <div class="rulecard"><ul>${v.rules.map(r=>`<li>${r}</li>`).join('')}</ul></div>
    <div class="event-banner" id="eventBanner"></div>
    <div class="timer" id="timer">--</div>
    <button class="cta" id="startBtn" onclick="startRound()">🔊 开始主持</button>
    <button class="cta ghost" onclick="stopAll();screenVariants()">换一个 🔄</button>
  </div></div>`;
}

function startRound(){
  const v = S.chosen;
  document.getElementById('startBtn').style.display = 'none';
  speak(v.speech, () => {
    speak('三，二，一，开始！', runTimer);
  });
}

function runTimer(){
  setState(1);
  let t = S.roundSec;
  const evAt = Math.floor(S.roundSec * (0.3 + Math.random() * 0.4));
  const evText = EVENTS[Math.floor(Math.random() * EVENTS.length)];
  const el = document.getElementById('timer');
  el.textContent = fmt(t);
  timerId = setInterval(() => {
    t--;
    if (!el.isConnected) return stopAll();
    el.textContent = fmt(t);
    if (t <= 10) el.classList.add('warn');
    if (t === evAt && !S.eventFired) {
      S.eventFired = true;
      S.evMark = S.roundSec - t;
      setState(2);
      const b = document.getElementById('eventBanner');
      b.style.display = 'block';
      b.textContent = '⚡ 随机事件：' + evText;
      speak('随机事件！' + evText, () => setState(1));
    }
    if (t <= 0) {
      stopAll();
      setState(3);
      speak('时间到！这一轮结束，报出你们的成绩吧！', screenResult);
    }
  }, 1000);
}
function fmt(t){ return String(Math.floor(t/60)).padStart(2,'0') + ':' + String(t%60).padStart(2,'0'); }
function setState(n){
  for (let i = 0; i < 4; i++) {
    const s = document.getElementById('st' + i);
    if (s) s.className = 'state' + (i === n ? ' on' : '');
  }
}
function stopAll(){ if (timerId) clearInterval(timerId); timerId = null; try{speechSynthesis.cancel();}catch(e){} }

/* 屏 6：战报 · 精彩片段 · 回流 */
function screenResult(){
  const v = S.chosen;
  const m = SUIT_META[v.suit];
  const fromDy = S.entry === 'douyin';
  const origin = fromDy ? '改造自「气球不落地接力挑战」' : '机制库即景生成';
  const ev = S.evMark || 45;
  const clipBlock = S.recording ? `
    <div class="panel">
      <div style="font-size:15px;font-weight:800;margin-bottom:4px">🎬 精彩片段已剪好（30 秒）</div>
      <div style="font-size:12px;color:var(--tx2)">发令台按自己的节奏表切片——它知道每个高潮在哪一秒：</div>
      <div class="clip">
        <div class="seg" style="background:linear-gradient(150deg,#3d68f5,#7c5cff)"><b>00:00</b>开始哨声 +5s<br>起跑混乱</div>
        <div class="seg" style="background:linear-gradient(150deg,#ff7a2f,#ff4d6d)"><b>00:${String(ev).padStart(2,'0')}</b>随机事件 ±10s<br>全场反应峰值</div>
        <div class="seg" style="background:linear-gradient(150deg,#7fb069,#3aad6a)"><b>01:20</b>最后 10s<br>冲刺与欢呼</div>
      </div>
      <button class="cta" style="margin-top:4px" onclick="alert('Demo 占位：预览通过后分享到微信群，或发布抖音（带 玩同款 tag）——发不发永远由用户决定')">预览成片 → 分享 / 发布</button>
    </div>` : `
    <button class="cta pp" onclick="alert('Demo 占位：生成战报卡片，带 同款开局 入口')">生成战报卡片 · 带「玩同款」入口</button>`;
  app.innerHTML = `
  <div class="screen">
    <div class="topbar"><span class="brand">本局结束</span><span>专属游戏记忆</span></div>
    <div class="report">
      <h3>🏆 ${v.name}</h3>
      <p>${v.desc}</p>
      <p class="origin">${origin} · ${m.icon} ${m.name} · ${S.players} 人 · ${S.relation}<br>这局只属于这张桌子、这群人、这个时刻。</p>
    </div>
    ${clipBlock}
    <button class="cta ghost" onclick="screenVariants()">再来一局（换个玩法）</button>
    <button class="cta ghost" onclick="screenDouyin()">回到抖音入口重新演示</button>
    <p class="hint">分享主路径：微信群/群聊 · 公开发布带「玩同款」tag 回流抖音是子集<br>下一个人点 tag → 在 TA 的场景拍摄 → 得到 TA 的专属版本</p>
  </div>`;
}

/* 入口：从抖音「玩同款」开始演示 */
screenDouyin();
