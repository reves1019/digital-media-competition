/* Original particle interaction for 字生万象. Canvas 2D; no external requests. */
(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const canvas = $('#particle-canvas');
  const ctx = canvas.getContext('2d');
  const wrap = $('#lab');
  const status = $('#studio-status');
  const count = matchMedia('(max-width: 700px)').matches ? 1700 : 2600;
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const palettes = [
    ['#e9b06d', '#cb6a4c', '#f1dcc0', '#b7aa7e'],
    ['#d5c58c', '#7fa99c', '#f2e3be', '#a2c4b7'],
    ['#efbd78', '#d89667', '#d9c6a6', '#86a497'],
    ['#d8caaf', '#ba7c57', '#e7b670', '#87aa9c']
  ];
  const scenes = [
    { text: '火', subtitle: '一簇光，也是一份温度。' },
    { text: '明', subtitle: '两束光，在这里相遇。' },
    { text: '家', subtitle: '屋檐之下，有人等你。' },
    { text: '字生万象', subtitle: '万千光点，写下心里的牵挂。' }
  ];
  const off = document.createElement('canvas');
  off.width = 1000; off.height = 640;
  const offCtx = off.getContext('2d', { willReadFrequently: true });
  let width = 600, height = 570, dpr = 1;
  let particles = [], targets = [], atmosphere;
  let sceneIndex = 0, activeText = scenes[0].text;
  let paused = reduceMotion.matches, last = performance.now();
  let autoTimer = null, recording = false, recorder = null;
  let clock = 0;

  function inform(message) { status.textContent = message; }

  function sample(text) {
    offCtx.clearRect(0, 0, off.width, off.height);
    const size = Math.min(475, 880 / Array.from(text).length);
    offCtx.font = `500 ${size}px "Noto Serif SC", "SimSun", "Microsoft YaHei", serif`;
    offCtx.textAlign = 'center'; offCtx.textBaseline = 'middle';
    offCtx.fillStyle = '#fff'; offCtx.fillText(text, 500, 300);
    const pixels = offCtx.getImageData(0, 0, off.width, off.height).data;
    const points = [];
    let left = 1000, right = 0, top = 640, bottom = 0;
    for (let y = 0; y < 640; y += 3) {
      for (let x = 0; x < 1000; x += 3) {
        if (pixels[(y * 1000 + x) * 4 + 3] > 110) {
          points.push({ x, y });
          left = Math.min(left, x); right = Math.max(right, x);
          top = Math.min(top, y); bottom = Math.max(bottom, y);
        }
      }
    }
    if (!points.length) return Array.from({ length: count }, () => ({ x: width / 2, y: height / 2 }));
    const scale = Math.min(width * .73 / Math.max(1, right - left), height * .55 / Math.max(1, bottom - top));
    return Array.from({ length: count }, () => {
      const p = points[Math.floor(Math.random() * points.length)];
      return {
        x: width / 2 + (p.x - (left + right) / 2) * scale + (Math.random() - .5) * 1.3,
        y: height * .48 + (p.y - (top + bottom) / 2) * scale + (Math.random() - .5) * 1.3
      };
    });
  }

  function resize() {
    const previousWidth = width, previousHeight = height;
    const rect = wrap.getBoundingClientRect();
    width = rect.width; height = rect.height;
    dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    atmosphere = ctx.createRadialGradient(width * .52, height * .47, 0, width * .52, height * .47, width * .7);
    atmosphere.addColorStop(0, '#172523'); atmosphere.addColorStop(.7, '#0b1211'); atmosphere.addColorStop(1, '#080d0d');
    targets = sample(activeText);
    particles.forEach((p, i) => {
      p.x = paused ? targets[i].x : p.x * width / previousWidth;
      p.y = paused ? targets[i].y : p.y * height / previousHeight;
    });
    paint();
  }

  function createParticles() {
    particles = Array.from({ length: count }, (_, i) => ({
      x: paused ? targets[i].x : Math.random() * width,
      y: paused ? targets[i].y : Math.random() * height,
      vx: 0, vy: 0, size: .45 + Math.random() * 1.15,
      phase: Math.random() * Math.PI * 2,
      color: palettes[0][i % 4]
    }));
  }

  function stopAuto() {
    clearInterval(autoTimer); autoTimer = null;
    $('#auto-play').setAttribute('aria-pressed', 'false');
    $('#auto-play').textContent = '连续演绎';
  }

  function showScene(index, custom) {
    sceneIndex = (index + scenes.length) % scenes.length;
    activeText = custom || scenes[sceneIndex].text;
    $('#scene-name').textContent = activeText;
    targets = sample(activeText);
    document.querySelectorAll('[data-scene]').forEach((button) => {
      button.setAttribute('aria-pressed', String(!custom && Number(button.dataset.scene) === sceneIndex));
    });
    particles.forEach((p, i) => {
      p.color = palettes[sceneIndex][i % 4];
      p.vx += (Math.random() - .5) * 16; p.vy += (Math.random() - .5) * 16;
      if (paused) { p.x = targets[i].x; p.y = targets[i].y; p.vx = p.vy = 0; }
    });
    paint();
    if (!recording) inform(custom ? `「${custom}」已经化作光点，可以保存字形卡。` : `当前：${activeText}。${scenes[sceneIndex].subtitle}`);
  }

  function paint() {
    if (!atmosphere) return;
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = atmosphere; ctx.fillRect(0, 0, width, height);
    // Quiet fixed stars give the letters a spatial frame without masking their silhouette.
    ctx.fillStyle = '#b7c6b3';
    for (let i = 0; i < 90; i++) {
      ctx.globalAlpha = .08 + (i % 5) * .015;
      ctx.fillRect(((i * 173.13) % 997) / 997 * width, ((i * 291.71) % 601) / 601 * height, 1, 1);
    }
    ctx.globalCompositeOperation = 'lighter';
    for (const p of particles) {
      const twinkle = .78 + .22 * Math.sin(clock * .0015 + p.phase);
      ctx.globalAlpha = twinkle;
      ctx.fillStyle = p.color;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size * twinkle, 0, Math.PI * 2); ctx.fill();
      if (p.size > 1.35) {
        ctx.globalAlpha = .075;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    if (recording) {
      ctx.font = '14px "Microsoft YaHei", sans-serif'; ctx.textAlign = 'left';
      ctx.fillStyle = '#d9c5a6'; ctx.fillText('字生万象', 32, 42);
      ctx.fillStyle = '#b8b8a6'; ctx.font = '12px "Microsoft YaHei", sans-serif';
      ctx.fillText(scenes[sceneIndex].subtitle, 32, height - 30);
    }
  }

  function render(now) {
    requestAnimationFrame(render);
    const dt = Math.min((now - last) / 1000, .034); last = now;
    if (paused || (document.hidden && !recording)) return;
    clock += dt * 1000;
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i], t = targets[i];
      p.vx += (t.x - p.x) * .011 * dt * 60;
      p.vy += (t.y - p.y) * .011 * dt * 60;
      const damping = Math.pow(.90, dt * 60);
      p.vx *= damping; p.vy *= damping;
      p.x += p.vx * dt * 60 + Math.sin(clock * .0013 + p.phase) * dt;
      p.y += p.vy * dt * 60 + Math.cos(clock * .001 + p.phase) * dt;
    }
    paint();
  }

  function syncPause() {
    $('#pause').textContent = paused ? '▷' : 'Ⅱ';
    $('#pause').setAttribute('aria-label', paused ? '继续动画' : '暂停动画');
    $('#pause').setAttribute('aria-pressed', String(paused));
  }

  function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = filename;
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  $('#pause').addEventListener('click', () => {
    paused = !paused; syncPause();
    inform(paused ? '画面已暂停。仍可以切换字形或保存字形卡。' : '动画已继续。');
  });
  $('#next').addEventListener('click', () => showScene(sceneIndex + 1));
  document.querySelectorAll('[data-scene]').forEach((button) => button.addEventListener('click', () => {
    stopAuto(); showScene(Number(button.dataset.scene));
  }));
  $('#word-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const text = $('#custom-word').value.trim();
    if (!/^[\p{Script=Han}]{1,4}$/u.test(text)) {
      $('#custom-word').setAttribute('aria-invalid', 'true');
      inform('请输入 1—4 个汉字，例如「故乡」或「山河无恙」。');
      $('#custom-word').focus(); return;
    }
    $('#custom-word').removeAttribute('aria-invalid');
    stopAuto(); showScene(3, text);
  });
  canvas.addEventListener('pointermove', (event) => {
    if (paused || recording) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left, y = event.clientY - rect.top;
    const radius = Math.min(width * .22, 130);
    for (const p of particles) {
      const dx = p.x - x, dy = p.y - y, distance = Math.hypot(dx, dy);
      if (distance < radius) {
        const force = (1 - distance / radius) * 2.4;
        p.vx += dx / Math.max(distance, 1) * force;
        p.vy += dy / Math.max(distance, 1) * force;
      }
    }
  });
  $('#auto-play').addEventListener('click', () => {
    if (autoTimer) { stopAuto(); inform('连续演绎已关闭。'); return; }
    paused = false; syncPause(); showScene(0);
    autoTimer = setInterval(() => { if (!paused) showScene(sceneIndex + 1); }, 4000);
    $('#auto-play').setAttribute('aria-pressed', 'true'); $('#auto-play').textContent = '停止演绎';
    inform('连续演绎中：每 4 秒切换一个字形，可随时暂停。');
  });
  $('#fullscreen').addEventListener('click', async () => {
    try {
      if (!wrap.requestFullscreen) { inform('此浏览器不支持页面全屏，可使用浏览器的全屏菜单。'); return; }
      await wrap.requestFullscreen();
    } catch { inform('未进入全屏，可继续在当前页面体验。'); }
  });
  $('#export-card').addEventListener('click', () => {
    const card = document.createElement('canvas'); card.width = 1080; card.height = 1350;
    const c = card.getContext('2d');
    c.fillStyle = '#0d1412'; c.fillRect(0, 0, 1080, 1350);
    const frame = { x: 56, y: 200, width: 968, height: 870 };
    const fit = Math.min(frame.width / canvas.width, frame.height / canvas.height);
    const cw = canvas.width * fit, ch = canvas.height * fit;
    c.drawImage(canvas, frame.x + (frame.width - cw) / 2, frame.y + (frame.height - ch) / 2, cw, ch);
    c.strokeStyle = '#495044'; c.lineWidth = 1; c.strokeRect(36, 36, 1008, 1278);
    c.fillStyle = '#e0c6a0'; c.font = '24px Outfit, sans-serif'; c.fillText('CHARACTERS IN LIGHT', 76, 100);
    c.font = '27px "Microsoft YaHei", sans-serif'; c.fillText('字生万象', 76, 143);
    c.fillStyle = '#f1e3cc'; c.font = '62px "SimSun", serif'; c.fillText(activeText, 76, 1170);
    c.fillStyle = '#a8aa99'; c.font = '22px "Microsoft YaHei", sans-serif'; c.fillText('万千光点，写下心里的牵挂。', 76, 1230);
    card.toBlob((blob) => {
      if (!blob) { inform('图片导出失败，请再试一次。'); return; }
      download(blob, `字生万象-${activeText}.png`);
      inform('已生成 1080 × 1350 字形卡，请在浏览器下载中查看。');
    }, 'image/png');
  });

  const recordButton = $('#record-video');
  function setRecordingControls(disabled) {
    ['#pause', '#next', '#auto-play', '#word-form button', '#custom-word', '#fullscreen'].forEach((selector) => { $(selector).disabled = disabled; });
    document.querySelectorAll('[data-scene]').forEach((button) => { button.disabled = disabled; });
    recordButton.disabled = disabled;
  }
  recordButton.addEventListener('click', () => {
    if (!window.MediaRecorder || !canvas.captureStream) { inform('此浏览器不支持录制。请用桌面 Edge 或 Chrome，或保存字形卡。'); return; }
    stopAuto(); paused = false; syncPause(); showScene(0);
    let stream;
    try {
      stream = canvas.captureStream(30);
      const mimeType = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find((mime) => MediaRecorder.isTypeSupported(mime));
      if (!mimeType) throw new Error('Unsupported format');
      recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6000000 });
      const chunks = []; let elapsed = 0, ended = false;
      recording = true; setRecordingControls(true); recordButton.textContent = '录制中 0 / 16 秒';
      inform('正在录制无声 WebM，请保持此页面在前台。完成后自动保存。');
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      const timer = setInterval(() => {
        elapsed++;
        recordButton.textContent = `录制中 ${elapsed} / 16 秒`;
        if (elapsed === 4 || elapsed === 8 || elapsed === 12) showScene(elapsed / 4);
        if (elapsed >= 16 && recorder.state !== 'inactive') recorder.stop();
      }, 1000);
      function finish() {
        if (ended) return; ended = true; clearInterval(timer);
        stream.getTracks().forEach((track) => track.stop());
        recording = false; setRecordingControls(false); recordButton.textContent = '录制 16 秒短片';
      }
      recorder.onstop = () => {
        finish();
        if (!chunks.length) { inform('录制未生成画面，请再试一次。'); return; }
        download(new Blob(chunks, { type: 'video/webm' }), '字生万象-16秒演绎.webm');
        inform('16 秒无声短片已生成。可用于预览，正式参赛成片仍需剪辑和音效。');
      };
      recorder.onerror = () => { finish(); inform('录制发生错误，请重新尝试或保存字形卡。'); };
      recorder.start(500);
    } catch {
      stream?.getTracks().forEach((track) => track.stop());
      recording = false; setRecordingControls(false); recordButton.textContent = '录制 16 秒短片';
      inform('此环境未能开始录制。请尝试桌面 Edge 或 Chrome。');
    }
  });

  const quotes = [
    ['“把熟悉的字拆成光点，再让它回到你面前。”', '创作手记 / 粒子书写'],
    ['“火、明、家，写的是字，也是生活里熟悉的温度。”', '创作手记 / 叙事线索'],
    ['“留下一个字，把此刻的心情带走。”', '创作手记 / 观众参与']
  ];
  let quoteIndex = 0;
  function quote(next) {
    quoteIndex = (next + quotes.length) % quotes.length;
    $('#quote').textContent = quotes[quoteIndex][0]; $('#quote-author').textContent = quotes[quoteIndex][1];
    if (window.gsap && !reduceMotion.matches) gsap.fromTo('#quote', { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: .4 });
  }
  $('#prev-quote').addEventListener('click', () => quote(quoteIndex - 1));
  $('#next-quote').addEventListener('click', () => quote(quoteIndex + 1));

  if (window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.utils.toArray('.word').forEach((word, index) => gsap.to(word, { opacity: 1, color: index % 3 === 0 ? '#efb866' : '#f2eadb', scrollTrigger: { trigger: '.manifesto', start: `top+=${index * 22} 80%`, end: `top+=${index * 22 + 150} 42%`, scrub: true } }));
      gsap.utils.toArray('.scene-image').forEach((image) => gsap.fromTo(image, { scale: .88, opacity: .5 }, { scale: 1, opacity: 1, ease: 'none', scrollTrigger: { trigger: image, start: 'top 95%', end: 'top 32%', scrub: true } }));
      gsap.fromTo('.action-inner', { clipPath: 'inset(0 6% 0 6%)' }, { clipPath: 'inset(0 0% 0 0%)', scrollTrigger: { trigger: '.action', start: 'top 90%', end: 'top 40%', scrub: true } });
    });
    mm.add('(min-width: 901px) and (prefers-reduced-motion: no-preference)', () => {
      ScrollTrigger.create({ trigger: '.story', pin: '.story-sticky', start: 'top top+=100', end: 'bottom bottom-=80', pinSpacing: false });
    });
  } else {
    document.querySelectorAll('.word').forEach((word) => { word.style.opacity = '1'; });
  }

  resize(); createParticles(); paint(); syncPause(); requestAnimationFrame(render);
  new ResizeObserver(resize).observe(wrap);
  document.fonts.ready.then(() => { resize(); window.ScrollTrigger?.refresh(); });
  if (reduceMotion.matches) inform('已按系统偏好暂停动态效果。可切换字形、保存卡片，或手动继续动画。');
})();
