<?php
/**
 * Kurage 設計下書き（kcadprep）— 成形品の説明から、AI が 3D の形と金型（キャビティ・コア）の下書きを作るデモ。
 * 公開先: https://proto.exbridge.jp/kcadprep/
 * 画面はこの1枚。設計の処理は api.php → 0.3 の kcadprep API（CadQuery を隔離して実行）。
 */
declare(strict_types=1);
header('Content-Type: text/html; charset=utf-8');
$SELF = 'https://proto.exbridge.jp/kcadprep/';
$TITLE = 'Kurage 設計下書き｜AIで金型の設計の下書きを作る';
$DESC = '成形品の形と寸法を日本語で書くと、AIがCADのコードを書き、3Dの形と金型のキャビティ・コアの下書き、ゲート・冷却穴、型締め力の目安までを作ります。STEPで書き出せます。AIはgemma4とCodexから選べます。';
$OG = 'https://proto.exbridge.jp/kcadprep/kcadprep-ogp.png';
$SHARE = '【Kurage 設計下書き】成形品の形を日本語で書くと、AIがCADで3Dの形と金型のキャビティ・コアの下書きを作り、STEPで書き出すシステムのデモです。';
$faq = [
    ['作った形は、そのまま金型の設計に使えますか？', 'いいえ。設計の下書き（たたき台）です。抜き勾配・パーティング面・ゲート・冷却穴は決まった手順で簡単に入れているだけで、湯流れや反りの解析、モールドベースや標準部品の選定はしていません。下書きを STEP で書き出し、お使いの CAD で仕上げてください。'],
    ['どんな形が得意ですか？', '箱・カバー・ケース・キャップ・トレーのように、寸法で形を決められる部品です。ボス・リブ・仕切り・穴・角の R も作れます。車の外装や家電の外観のような自由な曲面は得意ではありません。'],
    ['gemma4 と Codex は何が違いますか？', 'gemma4 は当社のサーバーで動く AI で、設計の内容を外に出さずに使えます。Codex は外部の AI で、形の組み方が複雑なときに強い AI です。このデモでは Codex は合言葉が必要です（商談の場でお伝えしています）。'],
    ['社内のサーバーで動かせますか？', '動かせます。CAD の処理（CadQuery）と gemma4 は社内のサーバーで動くので、図面や製品の情報を社外に出さずに使えます。御社の部品の種類や社内の設計の決まりに合わせて作り込むこともできます。'],
    ['型締め力の目安は、どう計算していますか？', '成形品を上から見た面積（投影面積）に、樹脂ごとの一般的な型内の圧力（PP 30MPa・ABS 40MPa・PC 50MPa など）を掛けた値です。成形機を選ぶ前のおおよその目安としてお使いください。'],
];
$ld = [
    ['@context' => 'https://schema.org', '@type' => 'SoftwareApplication', 'name' => 'Kurage 設計下書き', 'applicationCategory' => 'DesignApplication',
     'operatingSystem' => 'Web ブラウザ（社内サーバーにも設置可）', 'description' => $DESC, 'url' => $SELF, 'image' => $OG, 'inLanguage' => 'ja',
     'publisher' => ['@type' => 'Organization', 'name' => '株式会社エクスブリッジ', 'url' => 'https://exbridge.jp/']],
    ['@context' => 'https://schema.org', '@type' => 'FAQPage', 'mainEntity' => array_map(fn($x) => ['@type' => 'Question', 'name' => $x[0],
     'acceptedAnswer' => ['@type' => 'Answer', 'text' => $x[1]]], $faq)],
    ['@context' => 'https://schema.org', '@type' => 'BreadcrumbList', 'itemListElement' => [
     ['@type' => 'ListItem', 'position' => 1, 'name' => 'デモ一覧', 'item' => 'https://proto.exbridge.jp/'],
     ['@type' => 'ListItem', 'position' => 2, 'name' => 'Kurage 設計下書き', 'item' => $SELF]]],
];
function e(string $s): string { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
$examples = [
    ['箱形のケース', '外形80×50×30mm、肉厚2mmの箱形のケース。外側の角R3。天井の裏に、ねじ止め用のボスを4本（外径7mm・穴径3mm）。'],
    ['丸いキャップ', '直径60mm・高さ25mmの丸いキャップ。肉厚1.5mm。内側の天井から十字のリブ（厚さ1.2mm・高さ10mm）。'],
    ['仕切りのトレー', '長さ120mm・幅40mm・高さ15mmのトレー。上が開いていて、仕切りで3つの部屋に分ける。肉厚2mm。'],
    ['スイッチのカバー', '幅70mm・奥行き120mm・高さ8mmの薄いカバー。肉厚1.6mm。中央に20×30mmの角穴。四隅にφ4の取付穴のボス。'],
];
?><!doctype html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= e($TITLE) ?></title>
<meta name="description" content="<?= e($DESC) ?>">
<link rel="canonical" href="<?= e($SELF) ?>">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="website"><meta property="og:site_name" content="Kurage 設計下書き">
<meta property="og:title" content="<?= e($TITLE) ?>"><meta property="og:description" content="<?= e($DESC) ?>">
<meta property="og:url" content="<?= e($SELF) ?>"><meta property="og:image" content="<?= e($OG) ?>"><meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="https://kurage.exbridge.jp/images/kurage_mascot_simple_v2.png">
<?php foreach ($ld as $x): ?><script type="application/ld+json"><?= json_encode($x, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_HEX_TAG) ?></script>
<?php endforeach; ?>
<script>(function(){var s=document.createElement("script");s.src="https://kurage.exbridge.jp/simpletrack.php?url="+encodeURIComponent(location.href)+"&ref="+encodeURIComponent(document.referrer);s.async=true;document.head.appendChild(s)})();</script>
<style>
:root{color-scheme:light;--ink:#12202f;--sub:#4a5a6a;--line:#dfe6ee;--teal:#0a9a8f;--teal2:#077a71;--bg:#f5f8fb;--card:#fff;--warm:#fff7e6;--cav:#3d7bd9;--core:#e08a2b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Segoe UI","Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.75}
a{color:var(--teal2)}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
.top{background:#fff;border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 16px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink)}
.brand img{height:auto;object-fit:contain}
.brand b{display:block;font-size:17px;line-height:1.3}.brand small{display:block;font-size:12px;color:var(--sub)}
.top nav{display:flex;gap:14px;flex-wrap:wrap;font-size:13.5px}
.top nav a{text-decoration:none}.top nav .cta{background:var(--teal);color:#fff;padding:6px 12px;border-radius:8px;font-weight:700}
.hero{background:linear-gradient(135deg,#e9f7f5 0%,#f4f8ff 60%,#fff7e6 100%);border-bottom:1px solid var(--line)}
.hero .wrap{display:grid;grid-template-columns:minmax(0,1fr) 170px;gap:24px;align-items:center;padding:30px 16px 26px}
.hero .kicker{display:inline-block;background:#fff;border:1px solid #bfe6e1;color:var(--teal2);font-weight:700;font-size:12.5px;border-radius:999px;padding:2px 12px}
.hero h1{font-size:30px;line-height:1.35;margin:10px 0 8px}
.hero p{margin:0;color:var(--sub);font-size:15px}
.hero .mascot{width:170px;height:auto;object-fit:contain}
.share{display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px 0}
.share button,.share a{font:inherit;font-size:13px;border:1px solid var(--line);background:#fff;border-radius:8px;padding:5px 12px;cursor:pointer;color:var(--ink);text-decoration:none}
.grid{display:grid;grid-template-columns:minmax(0,420px) minmax(0,1fr);gap:18px;padding:18px 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.card h2{font-size:17px;margin:0 0 10px}
label.l{display:block;font-weight:700;font-size:14px;margin:12px 0 4px}
textarea{width:100%;min-height:130px;font:inherit;font-size:14.5px;border:2px solid #cfdae4;border-radius:10px;padding:10px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chips button{font:inherit;font-size:12.5px;border:1px solid #bfe6e1;background:#effaf8;color:var(--teal2);border-radius:999px;padding:3px 11px;cursor:pointer}
.seg{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.seg label{display:block;border:2px solid #cfdae4;border-radius:10px;padding:8px 10px;cursor:pointer;font-size:13px;line-height:1.5}
.seg input{margin-right:6px}.seg b{font-size:14px}
.seg label:has(input:checked){border-color:var(--teal);background:#effaf8}
select,input[type=password],input[type=text]{font:inherit;font-size:14px;border:2px solid #cfdae4;border-radius:10px;padding:7px 10px;width:100%}
.go{margin-top:14px;width:100%;background:var(--teal);color:#fff;border:0;border-radius:12px;padding:12px;font:inherit;font-weight:800;font-size:16px;cursor:pointer}
.go:disabled{background:#9fb8b5;cursor:wait}
.note{font-size:12.5px;color:var(--sub);margin:8px 0 0}
.err{background:#fdecec;border:1px solid #f3b9b9;color:#8a1c1c;border-radius:10px;padding:8px 12px;margin-top:10px;font-size:13.5px;white-space:pre-wrap}
#log{list-style:none;padding:0;margin:10px 0 0;font-size:13px;color:var(--sub)}
#log li{padding:2px 0}#log li b{color:var(--ink);font-weight:600;margin-right:6px}
.viewer{position:relative;background:linear-gradient(#f8fbff,#e9eff6);border:1px solid var(--line);border-radius:12px;height:430px;overflow:hidden}
.viewer canvas{display:block;width:100%;height:100%}
.viewer .empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--sub);font-size:14px;text-align:center;padding:16px}
.viewer .empty img{width:90px;height:auto;object-fit:contain;opacity:.85;margin-bottom:6px}
.toggles{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 0}
.toggles label{font-size:13px;border:1px solid var(--line);border-radius:8px;padding:4px 10px;background:#fff;cursor:pointer}
.sw{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}
.metrics div{background:#f7fafc;border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.metrics small{display:block;color:var(--sub);font-size:11.5px}.metrics b{font-size:15px}
.dl{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.dl a{font-size:13px;text-decoration:none;border:1px solid var(--teal);color:var(--teal2);border-radius:8px;padding:5px 11px;background:#fff}
.dl a.main{background:var(--teal);color:#fff}
details{margin-top:12px;font-size:13.5px}details pre{background:#0f1b27;color:#d8f3ee;padding:12px;border-radius:10px;overflow:auto;font-size:12.5px;max-height:360px}
.memo{background:var(--warm);border:1px solid #f1dfa6;border-radius:10px;padding:8px 12px;margin-top:12px;font-size:13.5px;white-space:pre-wrap}
section.s{padding:8px 16px 4px}
section.s h2{font-size:21px;margin:22px 0 10px}
.steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.steps .card b{display:block;color:var(--teal2);font-size:13px}.steps .card h3{font-size:15.5px;margin:2px 0 6px}.steps .card p{margin:0;font-size:13.5px;color:var(--sub)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.two .card h3{font-size:16px;margin:0 0 6px}.two ul{margin:0;padding-left:1.2em;font-size:14px}
.faq .card{margin-bottom:10px}.faq h3{font-size:15px;margin:0 0 4px}.faq p{margin:0;font-size:14px;color:var(--sub)}
.ctabox{display:flex;gap:16px;align-items:center;background:#fff;border:2px solid #bfe6e1;border-radius:16px;padding:18px;margin:20px 0}
.ctabox img{width:80px;height:auto;object-fit:contain}.ctabox p{margin:0 0 8px}
.ctabox a.b{display:inline-block;background:var(--teal);color:#fff;font-weight:800;border-radius:10px;padding:9px 16px;text-decoration:none}
footer{margin-top:28px;background:#12202f;color:#c9d6e2;font-size:13px}
footer .wrap{padding:18px 16px}footer a{color:#7fe0d4}
@media(max-width:900px){.grid{grid-template-columns:minmax(0,1fr)}.steps{grid-template-columns:repeat(2,minmax(0,1fr))}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.hero .wrap{grid-template-columns:minmax(0,1fr) 84px;gap:10px;padding:20px 16px}.hero .mascot{width:84px}.hero h1{font-size:22px}.hero p{font-size:14px}
 .two,.steps{grid-template-columns:minmax(0,1fr)}.viewer{height:320px}.top nav{font-size:12.5px;gap:10px}.ctabox{flex-direction:column;align-items:flex-start}}
</style>
</head><body>
<header class="top"><div class="wrap">
  <a class="brand" href="./">
    <img src="https://exbridge.jp/images/logo-mark-128.png" width="34" height="34" alt="株式会社エクスブリッジ">
    <img src="https://kurage.exbridge.jp/images/kurage_mascot_simple_v2.png" width="34" height="34" alt="">
    <span><b>Kurage 設計下書き</b><small>AIで金型の設計の下書き</small></span></a>
  <nav><a href="https://proto.exbridge.jp/#ref=kcadprep">デモ一覧</a><a href="https://exbridge.jp/#ref=kcadprep">エクスブリッジ</a><a class="cta" href="https://exbridge.jp/contact.php#ref=kcadprep">相談する</a></nav>
</div></header>

<div class="hero"><div class="wrap">
  <div>
    <span class="kicker">射出成形の金型づくりの下ごしらえを AI で</span>
    <h1>Kurage 設計下書き</h1>
    <p>成形品の形と寸法を日本語で書くと、AI が CAD のコードを書いて 3D の形を作り、金型のキャビティ（固定側）とコア（可動側）に分けた下書きを作ります。ゲートと冷却穴の位置、重さ・投影面積・型締め力の目安まで出し、STEP で書き出せます。</p>
  </div>
  <img class="mascot" src="https://kurage.exbridge.jp/images/kurage_mascot_simple_v2.png" width="170" height="170" alt="Kurage のマスコット">
</div></div>
<div class="wrap"><div class="share" style="padding-left:0;padding-right:0">
  <button type="button" id="copy" data-copy="<?= e($SHARE . "\n" . $SELF) ?>">紹介文とURLをコピー</button>
  <a target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?text=<?= rawurlencode($SHARE) ?>&url=<?= rawurlencode($SELF) ?>">Xで共有</a>
</div></div>

<div class="wrap"><div class="grid" style="padding-left:0;padding-right:0">
  <div class="card">
    <h2>成形品の説明</h2>
    <div class="chips" id="ex"><?php foreach ($examples as $x): ?><button type="button" data-t="<?= e($x[1]) ?>"><?= e($x[0]) ?></button><?php endforeach; ?></div>
    <label class="l" for="req">形・寸法・肉厚・ボスやリブなど</label>
    <textarea id="req" maxlength="600"><?= e($examples[0][1]) ?></textarea>
    <label class="l">設計する AI</label>
    <div class="seg">
      <label><input type="radio" name="engine" value="gemma" checked><b>gemma4</b><br>当社のサーバーで動く AI。設計の内容を外に出さない</label>
      <label><input type="radio" name="engine" value="codex"><b>Codex</b><br>外部の AI。複雑な形に強い（合言葉が必要）</label>
    </div>
    <div id="passbox" style="display:none"><label class="l" for="pass">Codex の合言葉</label><input type="password" id="pass" autocomplete="off" placeholder="商談の場でお伝えしています"></div>
    <label class="l" for="mat">樹脂（重さと型締め力の目安に使います）</label>
    <select id="mat"><option value="ABS">ABS</option><option value="PP">PP（ポリプロピレン）</option><option value="PC">PC（ポリカーボネート）</option><option value="PA66">PA66（ナイロン）</option><option value="POM">POM（ポリアセタール）</option></select>
    <button class="go" id="go" type="button">設計の下書きを作る</button>
    <p class="note">gemma4 で15〜60秒ほど、Codex で30秒ほどかかります。エラーが出たときや、できた形の大きさが説明と合わないときは、AI がそれを読んで自動で直します。</p>
    <div id="err" class="err" style="display:none"></div>
    <ul id="log"></ul>
  </div>
  <div class="card">
    <h2>3Dの下書き</h2>
    <div class="viewer" id="viewer"><div class="empty" id="empty"><img src="https://kurage.exbridge.jp/images/kurage_mascot_simple_v2.png" width="90" height="90" alt="">左で説明を書いて「設計の下書きを作る」を押すと、ここに 3D の形が出ます。<br>マウスやタッチで回せます。</div></div>
    <div class="toggles" id="tg" style="display:none">
      <label><input type="checkbox" data-k="part" checked><span class="sw" style="background:#7d8894"></span>成形品</label>
      <label><input type="checkbox" data-k="cavity" checked><span class="sw" style="background:var(--cav)"></span>キャビティ（固定側）</label>
      <label><input type="checkbox" data-k="core" checked><span class="sw" style="background:var(--core)"></span>コア（可動側）</label>
      <label><input type="checkbox" id="open" checked>型を開いて見る</label>
    </div>
    <div class="metrics" id="mt"></div>
    <div class="dl" id="dl"></div>
    <div id="memo" class="memo" style="display:none"></div>
    <details id="codebox" style="display:none"><summary>AI が書いた CAD のコード（CadQuery）</summary><pre id="code"></pre></details>
  </div>
</div></div>

<section class="s wrap">
  <h2>何をしているか</h2>
  <div class="steps">
    <div class="card"><b>1</b><h3>説明を読む</h3><p>形・寸法・肉厚・ボスやリブの指定を、AI が読み取ります。指定の無い寸法は、その製品として自然な値を決めて「設計メモ」に残します。</p></div>
    <div class="card"><b>2</b><h3>CAD のコードを書く</h3><p>AI が CadQuery（オープンソースの CAD）のコードを書き、隔離した環境で実行して 3D の形を作ります。エラーや寸法の食い違いは、AI に返して直させます。</p></div>
    <div class="card"><b>3</b><h3>型を上下に分ける</h3><p>成形品の口の面をパーティング面にして、キャビティ（固定側）とコア（可動側）に分けます。ゲートの穴と冷却穴も入れます。</p></div>
    <div class="card"><b>4</b><h3>目安を出して書き出す</h3><p>体積・重さ・投影面積・型締め力の目安を出し、成形品・キャビティ・コアを STEP（ほかの CAD で開ける形式）で書き出します。</p></div>
  </div>
  <h2>できること・まだできないこと</h2>
  <div class="two">
    <div class="card"><h3>できること</h3><ul><li>箱・カバー・ケース・キャップ・トレーのような、寸法で決まる形</li><li>肉厚・角の R・ボス・リブ・仕切り・穴</li><li>キャビティ・コアの簡単な分割、ゲート・冷却穴</li><li>重さ・投影面積・型締め力の目安</li><li>STEP・STL での書き出し</li></ul></div>
    <div class="card"><h3>まだできないこと（人が仕上げるところ）</h3><ul><li>車の外装・家電の外観のような自由な曲面</li><li>アンダーカット（スライド・傾斜ピン）の判断</li><li>湯流れ・反り・ひけの解析</li><li>モールドベース・エジェクタピンなど標準部品の選定</li><li>そのまま加工に使える精度の図面</li></ul></div>
  </div>
  <h2>よくある質問</h2>
  <div class="faq"><?php foreach ($faq as $x): ?><div class="card"><h3><?= e($x[0]) ?></h3><p><?= e($x[1]) ?></p></div><?php endforeach; ?></div>
  <div class="ctabox">
    <img src="https://kurage.exbridge.jp/images/kurage_mascot_simple_v2.png" width="80" height="80" alt="">
    <div><p><b>御社の部品と設計の決まりに合わせて作り込めます。</b>よく作る部品の型、社内の標準寸法、使っている CAD への書き出しに合わせて、社内のサーバーで動く形でお作りします。</p>
    <a class="b" href="https://exbridge.jp/contact.php#ref=kcadprep">設計の下書きを相談する</a></div>
  </div>
</section>
<footer><div class="wrap">運営：<a href="https://exbridge.jp/#ref=kcadprep">株式会社エクスブリッジ</a>（名古屋市瑞穂区）　AI を使った業務システムの開発　｜　<a href="https://proto.exbridge.jp/#ref=kcadprep">デモ一覧</a>　｜　CAD の処理は CadQuery（Apache License 2.0）を使っています</div></footer>

<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script>
<script type="module" src="app.js?v=1"></script>
</body></html>
