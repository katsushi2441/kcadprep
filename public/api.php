<?php
/**
 * Kurage 設計下書き — 0.3 の API への中継。ブラウザからは同じドメインの api.php だけを呼ぶ。
 *   POST api.php?a=create  {request, engine, material, passcode}
 *   GET  api.php?a=job&id=…
 *   GET  api.php?a=file&id=…&name=part.stl
 * 合言葉（API トークン）は kcadprep_config.php（配置のときに書き込む。リポジトリには置かない）。
 */
declare(strict_types=1);
$cfg = require __DIR__ . '/kcadprep_config.php';
$a = (string)($_GET['a'] ?? '');
$id = (string)($_GET['id'] ?? '');

function out(int $code, string $body, string $type = 'application/json; charset=utf-8'): void
{
    http_response_code($code);
    header('Content-Type: ' . $type);
    header('Cache-Control: no-store');
    header('X-Robots-Tag: noindex');
    echo $body;
    exit;
}

function call(array $cfg, string $method, string $path, ?string $body = null, int $timeout = 20): array
{
    $ch = curl_init(rtrim($cfg['api'], '/') . $path);
    $h = ['X-KCADPREP-TOKEN: ' . $cfg['token'], 'X-Client-IP: ' . ($_SERVER['REMOTE_ADDR'] ?? '')];
    if ($body !== null) { $h[] = 'Content-Type: application/json'; }
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => $timeout, CURLOPT_CONNECTTIMEOUT => 6,
        CURLOPT_CUSTOMREQUEST => $method, CURLOPT_HTTPHEADER => $h, CURLOPT_HEADER => true]);
    if ($body !== null) { curl_setopt($ch, CURLOPT_POSTFIELDS, $body); }
    $res = curl_exec($ch);
    if ($res === false) { return [503, '', '']; }
    $code = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $hs = (int)curl_getinfo($ch, CURLINFO_HEADER_SIZE);
    $ctype = (string)curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
    curl_close($ch);
    return [$code, substr($res, $hs), $ctype];
}

if ($a === 'create' && ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    $in = json_decode((string)file_get_contents('php://input'), true);
    if (!is_array($in)) { out(400, json_encode(['detail' => '入力が読めませんでした'])); }
    $body = json_encode(['request' => (string)($in['request'] ?? ''), 'engine' => (string)($in['engine'] ?? 'gemma'),
        'material' => (string)($in['material'] ?? 'ABS'), 'passcode' => (string)($in['passcode'] ?? '')], JSON_UNESCAPED_UNICODE);
    [$c, $b] = call($cfg, 'POST', '/api/jobs', $body);
    if ($c === 503) { out(503, json_encode(['detail' => '設計のサーバーにつながりませんでした。少し待ってからお試しください'], JSON_UNESCAPED_UNICODE)); }
    out($c, $b);
}
if (!preg_match('/^[0-9]{8}-[0-9]{6}-[a-f0-9]{6}$/', $id)) { out(404, json_encode(['detail' => 'not found'])); }
if ($a === 'job') {
    [$c, $b] = call($cfg, 'GET', '/api/jobs/' . $id);
    if ($c === 503) { out(503, json_encode(['detail' => '設計のサーバーにつながりませんでした'], JSON_UNESCAPED_UNICODE)); }
    out($c, $b);
}
if ($a === 'file') {
    $name = (string)($_GET['name'] ?? '');
    if (!preg_match('/^(part|cavity|core)\.(stl|step)$|^part_code\.py$/', $name)) { out(404, '{}'); }
    [$c, $b, $t] = call($cfg, 'GET', '/api/jobs/' . $id . '/' . $name, null, 60);
    if ($c !== 200) { out($c ?: 502, '{}'); }
    if (!empty($_GET['dl'])) { header('Content-Disposition: attachment; filename="kcadprep-' . $id . '-' . $name . '"'); }
    out(200, $b, $t ?: 'application/octet-stream');
}
out(404, '{}');
