import React from 'react'
import ReactDOM from 'react-dom/client'
import './theme.css'
import App from './App.jsx'

const style = document.createElement('style')
style.textContent = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

  :root {
    --cx: -600px;
    --cy: -600px;
    --p1: #7c3aed;
    --p1h: #8b5cf6;
    --p2: #a78bfa;
    --p3: #c4b5fd;
    --p4: #ede9fe;
    --c1: #06b6d4;
    --c2: #22d3ee;
    --c3: #67e8f9;
    --p1-rgb: 124,58,237;
    --p2-rgb: 167,139,250;
    --p3-rgb: 196,181,253;
    --c1-rgb: 6,182,212;
    --app-bg: #04050d;
    --app-surface: rgba(7, 8, 12, 0.95);
    --app-surface-strong: rgba(7, 8, 12, 0.98);
    --app-text: #f8fafc;
    --app-muted: rgba(255,255,255,0.62);
    --app-muted-strong: rgba(255,255,255,0.35);
    --app-border: rgba(139,92,246,0.12);
    --app-pill-bg: rgba(139,92,246,0.08);
    --app-pill-border: rgba(139,92,246,0.16);
    --app-card-bg: rgba(255,255,255,0.05);
    --app-card-border: rgba(255,255,255,0.07);
    --app-nav-text: rgba(255,255,255,0.78);
    --app-panel-bg: rgba(8, 10, 20, 0.82);
    --app-panel-border: rgba(255,255,255,0.08);
    --app-shadow: rgba(0, 0, 0, 0.24);
    --app-accent: #7c3aed;
    --app-accent-2: #22d3ee;
    --app-surface-soft: rgba(255,255,255,0.06);
    --bg-02: rgba(255,255,255,0.02);
    --bg-022: rgba(255,255,255,0.022);
    --bg-025: rgba(255,255,255,0.025);
    --bg-04: rgba(255,255,255,0.04);
    --bg-07: rgba(255,255,255,0.07);
    --text-03: rgba(255,255,255,0.03);
    --text-04: rgba(255,255,255,0.04);
    --text-05: rgba(255,255,255,0.05);
    --text-06: rgba(255,255,255,0.06);
    --text-07: rgba(255,255,255,0.07);
    --text-08: rgba(255,255,255,0.08);
    --text-09: rgba(255,255,255,0.09);
    --text-10: rgba(255,255,255,0.1);
    --text-20: rgba(255,255,255,0.2);
    --text-22: rgba(255,255,255,0.22);
    --text-25: rgba(255,255,255,0.25);
    --text-28: rgba(255,255,255,0.28);
    --text-30: rgba(255,255,255,0.3);
    --text-32: rgba(255,255,255,0.32);
    --text-35: rgba(255,255,255,0.35);
    --text-38: rgba(255,255,255,0.38);
    --text-40: rgba(255,255,255,0.4);
    --text-42: rgba(255,255,255,0.42);
    --text-45: rgba(255,255,255,0.45);
    --text-50: rgba(255,255,255,0.5);
    --text-55: rgba(255,255,255,0.55);
    --text-62: rgba(255,255,255,0.62);
    --text-70: rgba(255,255,255,0.7);
    --text-85: rgba(255,255,255,0.85);
    --text-88: rgba(255,255,255,0.88);
    --bg-03: rgba(255,255,255,0.03);
    --bg-05: rgba(255,255,255,0.05);
    --bg-06: rgba(255,255,255,0.06);
    --bg-08: rgba(255,255,255,0.08);
    --bg-10: rgba(255,255,255,0.1);
    --bg-12: rgba(255,255,255,0.12);
    --bg-15: rgba(255,255,255,0.15);
    --bg-20: rgba(255,255,255,0.2);
    --bg-25: rgba(255,255,255,0.25);
    --heading-gradient: linear-gradient(135deg, #ffffff 20%, #c4b5fd 55%, #67e8f9 100%);
  }

  :root[data-theme='light'] {
    --app-bg: linear-gradient(135deg, #f7f9ff 0%, #eef4ff 45%, #fdfbff 100%);
    --app-surface: rgba(124,58,237,0.12);
    --app-surface-strong: rgba(124,58,237,0.16);
    --app-text: #000a1a;
    --app-muted: rgba(0,10,26,0.72);
    --app-muted-strong: rgba(0,10,26,0.64);
    --app-border: rgba(124,58,237,0.24);
    --app-pill-bg: rgba(124,58,237,0.18);
    --app-pill-border: rgba(124,58,237,0.3);
    --app-card-bg: rgba(124,58,237,0.14);
    --app-card-border: rgba(124,58,237,0.28);
    --app-nav-text: rgba(0,10,26,0.82);
    --app-panel-bg: rgba(124,58,237,0.1);
    --app-panel-border: rgba(124,58,237,0.22);
    --app-shadow: rgba(0,10,26,0.12);
    --app-accent: #6d28d9;
    --app-accent-2: #0f766e;
    --app-surface-soft: rgba(124,58,237,0.08);
    --bg-02: rgba(124,58,237,0.06);
    --bg-022: rgba(124,58,237,0.065);
    --bg-025: rgba(124,58,237,0.07);
    --bg-04: rgba(124,58,237,0.09);
    --bg-07: rgba(124,58,237,0.13);
    --bg-03: rgba(124,58,237,0.08);
    --bg-05: rgba(124,58,237,0.1);
    --bg-06: rgba(124,58,237,0.12);
    --bg-08: rgba(124,58,237,0.14);
    --bg-10: rgba(124,58,237,0.16);
    --bg-12: rgba(124,58,237,0.18);
    --bg-15: rgba(124,58,237,0.2);
    --bg-20: rgba(124,58,237,0.24);
    --bg-25: rgba(124,58,237,0.28);
    --heading-gradient: #000a1a;
    --text-03: rgba(0,10,26,0.12);
    --text-04: rgba(0,10,26,0.14);
    --text-05: rgba(0,10,26,0.16);
    --text-06: rgba(0,10,26,0.18);
    --text-07: rgba(0,10,26,0.2);
    --text-08: rgba(0,10,26,0.22);
    --text-09: rgba(0,10,26,0.24);
    --text-10: rgba(0,10,26,0.26);
    --text-20: rgba(0,10,26,0.38);
    --text-22: rgba(0,10,26,0.4);
    --text-25: rgba(0,10,26,0.44);
    --text-28: rgba(0,10,26,0.48);
    --text-30: rgba(0,10,26,0.5);
    --text-32: rgba(0,10,26,0.52);
    --text-35: rgba(0,10,26,0.56);
    --text-38: rgba(0,10,26,0.6);
    --text-40: rgba(0,10,26,0.62);
    --text-42: rgba(0,10,26,0.64);
    --text-45: rgba(0,10,26,0.66);
    --text-50: rgba(0,10,26,0.72);
    --text-55: rgba(0,10,26,0.76);
    --text-62: rgba(0,10,26,0.85);
    --text-70: rgba(0,10,26,0.92);
    --text-85: rgba(0,10,26,0.98);
    --text-88: rgba(0,10,26,1);
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html, body, #root {
    height: 100%;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--app-bg);
    color: var(--app-text);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    transition: background 0.3s ease, color 0.3s ease;
  }

  html[data-theme='light'] body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: radial-gradient(circle at top left, rgba(124,58,237,0.14), transparent 30%), radial-gradient(circle at bottom right, rgba(6,182,212,0.15), transparent 35%);
    pointer-events: none;
    z-index: 0;
  }

  /* Cursor glow — dual-tone: violet + faint cyan tail */
  .cursor-glow {
    position: fixed;
    top: 0; left: 0;
    width: 800px; height: 800px;
    transform: translate(calc(var(--cx) - 400px), calc(var(--cy) - 400px));
    background: radial-gradient(
      circle at center,
      rgba(var(--p1-rgb), 0.09) 0%,
      rgba(var(--p1-rgb), 0.04) 30%,
      rgba(var(--c1-rgb), 0.02) 55%,
      transparent 68%
    );
    border-radius: 50%;
    pointer-events: none;
    z-index: 0;
    will-change: transform;
  }

  /* Subtle noise texture for depth */
  html::after {
    content: '';
    position: fixed;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 999;
    opacity: 0.35;
  }

  ::-webkit-scrollbar { width: 3px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.25); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(139,92,246,0.4); }

  /* Animations */
  @keyframes pageEnter {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.3; }
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0.65); opacity: 0.4; }
    40%           { transform: scale(1);    opacity: 1; }
  }
  @keyframes kpiCount {
    0%   { opacity: 0.4; transform: translateY(4px) scale(0.96); }
    60%  { transform: translateY(-1px) scale(1.02); }
    100% { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes kpiFlash {
    0%   { box-shadow: 0 0 0 0 rgba(var(--p1-rgb),0); }
    30%  { box-shadow: 0 0 0 3px rgba(var(--p1-rgb),0.35); }
    100% { box-shadow: 0 0 0 0 rgba(var(--p1-rgb),0); }
  }
  @keyframes criticalPulse {
    0%, 100% { box-shadow: 0 0 30px rgba(var(--p1-rgb),0.18), 0 0 60px rgba(var(--p1-rgb),0.08), inset 0 1px 0 rgba(255,255,255,0.08); }
    50%       { box-shadow: 0 0 50px rgba(var(--p1-rgb),0.35), 0 0 100px rgba(var(--p1-rgb),0.16), inset 0 1px 0 rgba(255,255,255,0.12); }
  }
  @keyframes ringPulse {
    0%, 100% { opacity: 0.4; transform: scale(1); }
    50%       { opacity: 0.95; transform: scale(1.006); }
  }
  @keyframes drift1 {
    0%   { transform: translate(0px, 0px) scale(1); }
    33%  { transform: translate(40px, -28px) scale(1.03); }
    66%  { transform: translate(-18px, 18px) scale(0.97); }
    100% { transform: translate(0px, 0px) scale(1); }
  }
  @keyframes drift2 {
    0%   { transform: translate(0px, 0px) scale(1); }
    33%  { transform: translate(-45px, 22px) scale(0.96); }
    66%  { transform: translate(28px, -12px) scale(1.04); }
    100% { transform: translate(0px, 0px) scale(1); }
  }
  @keyframes lineShimmer {
    0%   { opacity: 0.3; }
    50%  { opacity: 0.9; }
    100% { opacity: 0.3; }
  }
  @keyframes alertSlide {
    from { transform: translateY(-100%); opacity: 0; }
    to   { transform: translateY(0); opacity: 1; }
  }
  @keyframes logEntry {
    from { opacity: 0; transform: translateX(-6px); }
    to   { opacity: 1; transform: translateX(0); }
  }
  @keyframes scorePop {
    0%   { transform: scale(0.92); }
    60%  { transform: scale(1.04); }
    100% { transform: scale(1); }
  }
  @keyframes toastSlide {
    from { transform: translateX(60px); opacity: 0; }
    to   { transform: translateX(0); opacity: 1; }
  }
  @keyframes toastDrain {
    from { width: 100%; }
    to   { width: 0%; }
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0; }
  }

  .tilt-card {
    transition: transform 0.1s ease;
    will-change: transform;
    transform-style: preserve-3d;
  }

  .page-wrapper {
    animation: pageEnter 0.38s cubic-bezier(0.22, 1, 0.36, 1) both;
  }

  .nav-btn {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 10px 12px;
    border-radius: 10px;
    width: 100%;
    border: 1px solid transparent;
    cursor: pointer;
    font-family: inherit;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
    color: var(--app-muted);
    background: transparent;
    transition: all 0.18s ease;
  }
  .nav-btn:hover {
    background: var(--app-surface-soft);
    color: var(--app-text);
    border-color: var(--app-border);
  }
  .nav-btn.active {
    background: linear-gradient(90deg, rgba(124,58,237,0.14), rgba(34,211,238,0.1));
    color: var(--app-accent);
    font-weight: 700;
    border-color: rgba(124,58,237,0.22);
    box-shadow: inset 3px 0 0 var(--app-accent);
  }

  button { font-family: inherit; }
  input  { font-family: inherit; }

  .mono { font-family: 'JetBrains Mono', 'Fira Code', monospace; }
`
document.head.appendChild(style)

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)