import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

// SVG artwork and all motion are generated in code. No Blender or external PNG assets.
// Deliberately stylized vector art: not a photorealistic or AI-painted warrior.
const clamp = {extrapolateLeft:'clamp' as const,extrapolateRight:'clamp' as const};
const range = (f:number,a:number,b:number,x:number,y:number) => interpolate(f,[a,b],[x,y],clamp);

const Warrior:React.FC<{frame:number}> = ({frame}) => {
  const raise=range(frame,20,94,0,1);
  const shoulder=-20-raise*112;
  const elbow=-15+raise*26;
  const sword=-25+raise*66;
  const breathe=Math.sin(frame/15)*5;
  return <g transform={`translate(510 1170) translate(0 ${breathe})`}>
    <defs>
      <linearGradient id="coat" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f6e4bd"/><stop offset=".52" stopColor="#c8a477"/><stop offset="1" stopColor="#72533d"/></linearGradient>
      <linearGradient id="steel" x1="0" y1="0" x2="1" y2="0"><stop stopColor="#526774"/><stop offset=".45" stopColor="#f3f7ef"/><stop offset="1" stopColor="#8397a0"/></linearGradient>
      <linearGradient id="turban" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#ffb04c"/><stop offset=".6" stopColor="#c75020"/><stop offset="1" stopColor="#782719"/></linearGradient>
    </defs>
    {/* Back cape and legs */}
    <path d="M-145 -240 Q-280 -150 -350 185 Q-185 125 -90 70Z" fill="#ad431f" stroke="#4b281e" strokeWidth="9"/>
    <path d="M-105 65 L-118 430 L-23 430 L12 90 M30 85 L55 430 L148 430 L130 45" fill="#d8c19a" stroke="#4c3d33" strokeWidth="12"/>
    <path d="M-124 414 L-136 506 Q-76 520 -4 507 L-22 416Z M53 414 L46 507 Q110 521 166 504 L145 414Z" fill="#543a2c" stroke="#251d1b" strokeWidth="10"/>
    <path d="M-175 -235 Q-185 -85 -155 140 Q0 178 168 135 Q145 -20 178 -235 Q40 -292 -175 -235Z" fill="url(#coat)" stroke="#3e2b24" strokeWidth="12"/>
    <path d="M-18 -248 L18 144" stroke="#8d6445" strokeWidth="14"/>
    {[-160,-100,-40,20,80].map((y,i)=><circle key={i} cx="20" cy={y} r="11" fill="#d8a63c" stroke="#6b4822" strokeWidth="4"/>)}
    <path d="M-178 -20 Q0 0 177 -16 L173 45 Q0 64 -180 43Z" fill="#a52e20" stroke="#e4a444" strokeWidth="10"/>
    <path d="M100 35 Q210 205 150 340 L100 320 L72 43" fill="#f18b2c" stroke="#6b2e1b" strokeWidth="8"/>
    {/* Left arm */}
    <g transform="translate(-158 -225) rotate(14)">
      <path d="M-25 0 Q-70 90 -33 180 L20 180 Q50 85 34 0Z" fill="url(#coat)" stroke="#513b2c" strokeWidth="10"/>
      <g transform="translate(-8 165) rotate(-12)"><path d="M-25 0 L-25 180 L26 180 L32 0Z" fill="#65717b" stroke="#2c333c" strokeWidth="10"/><ellipse cy="185" rx="30" ry="37" fill="#a66c4c" stroke="#4e2d22" strokeWidth="8"/></g>
    </g>
    {/* Right arm, sword and forearm share joint hierarchy */}
    <g transform={`translate(160 -225) rotate(${shoulder})`}>
      <path d="M-30 0 Q-55 80 -27 176 L29 176 Q54 65 31 0Z" fill="url(#coat)" stroke="#503a2a" strokeWidth="11"/>
      <ellipse cy="0" rx="43" ry="33" fill="#bd8b45" stroke="#6e4528" strokeWidth="8"/>
      <g transform={`translate(0 163) rotate(${elbow})`}>
        <path d="M-25 0 L-30 165 L30 165 L26 0Z" fill="#65727d" stroke="#29323b" strokeWidth="10"/>
        <path d="M-26 30 L26 30 M-28 140 L28 140" stroke="#c4a86e" strokeWidth="9"/>
        <g transform={`translate(0 167) rotate(${sword})`}>
          <ellipse cy="25" rx="29" ry="38" fill="#9f6344" stroke="#4c2a20" strokeWidth="8"/>
          <path d="M-11 -20 L11 -20 L10 66 L-10 66Z" fill="#4e2d22" stroke="#d6a749" strokeWidth="7"/>
          <path d="M-72 65 Q0 40 72 65" stroke="#e0ad48" strokeWidth="17" fill="none" strokeLinecap="round"/>
          <path d="M-18 64 Q-25 185 -10 355 L0 398 L12 353 Q26 182 18 64Z" fill="url(#steel)" stroke="#263b44" strokeWidth="8"/>
          <path d="M0 80 L0 350" stroke="#fff6d6" strokeWidth="5" opacity=".8"/>
        </g>
      </g>
    </g>
    {/* Head and layered turban */}
    <path d="M-40 -265 L-36 -340 L40 -340 L45 -267" fill="#a96c4b" stroke="#553424" strokeWidth="9"/>
    <ellipse cy="-405" rx="100" ry="126" fill="#a66a49" stroke="#4a2e24" strokeWidth="11"/>
    <path d="M-87 -385 Q-90 -290 5 -279 Q102 -308 90 -385 Q43 -350 15 -370 Q-12 -344 -87 -385Z" fill="#2a211d"/>
    <path d="M-80 -394 Q-42 -424 -5 -388 Q42 -425 85 -394" fill="none" stroke="#291e19" strokeWidth="22"/>
    <path d="M-47 -427 L-13 -432 M27 -432 L62 -427" stroke="#261c19" strokeWidth="12" strokeLinecap="round"/>
    <circle cx="-28" cy="-412" r="7" fill="#211918"/><circle cx="43" cy="-412" r="7" fill="#211918"/>
    <path d="M-2 -407 L-15 -378 L9 -373" stroke="#6f402f" strokeWidth="9" fill="none"/>
    <path d="M-105 -488 Q-126 -574 -60 -607 Q18 -652 103 -574 Q127 -520 105 -488 Q-1 -468 -105 -488Z" fill="url(#turban)" stroke="#5d2d1e" strokeWidth="12"/>
    {[-70,-28,15,55].map((x,i)=><path key={i} d={`M${x-20} -505 Q${x+12} -558 ${x+32} -593`} fill="none" stroke={i%2?'#f6a044':'#a63821'} strokeWidth="20" opacity=".85"/>)}
    <path d="M65 -574 Q112 -647 123 -682 Q147 -622 97 -550" fill="#e5b65a" stroke="#6b4624" strokeWidth="7"/>
    <ellipse cx="82" cy="-530" rx="18" ry="23" fill="#f6cb62" stroke="#633b1d" strokeWidth="7"/>
  </g>;
};

export const WarriorShort:React.FC=()=>{
  const frame=useCurrentFrame();
  const zoom=range(frame,0,150,1,1.11);
  const drift=range(frame,0,150,-40,30);
  const glow=0.35+Math.sin(frame/24)*0.06;
  const particles=Array.from({length:35},(_,i)=>({
    x:(i*191+73)%1080,y:(i*337+83)%1920,r:2+(i%5),
    dx:Math.sin(i*2.7)*frame*0.9,dy:-frame*(0.5+i%3)*0.5
  }));
  return <AbsoluteFill style={{backgroundColor:'#1c272a',overflow:'hidden'}}>
    <svg viewBox="0 0 1080 1920" width="100%" height="100%">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#17242d"/><stop offset=".58" stopColor="#915339"/><stop offset="1" stopColor="#e9a65b"/></linearGradient>
        <radialGradient id="sun"><stop stopColor="#fff5c2" stopOpacity=".95"/><stop offset=".4" stopColor="#ffbf62" stopOpacity=".6"/><stop offset="1" stopColor="#ff9b45" stopOpacity="0"/></radialGradient>
      </defs>
      <rect width="1080" height="1920" fill="url(#sky)"/>
      <circle cx="800" cy="680" r="480" fill="url(#sun)" opacity={glow*2}/>
      <g transform={`translate(${drift} 0)`} opacity=".5" fill="#293137">
        <path d="M-100 1020 L110 860 L250 980 L405 770 L590 1000 L800 825 L1200 1030 L1200 1600 L-100 1600Z"/>
      </g>
      <path d="M0 1270 Q260 1190 510 1270 Q810 1150 1080 1270 L1080 1920 L0 1920Z" fill="#4d342c"/>
      <g opacity=".7" fill="#2a2726">
        <path d="M0 1170 L0 970 L170 970 L170 1030 L250 1030 L250 930 L350 930 L350 1170Z"/>
        <path d="M780 1200 L780 930 L860 930 L860 850 L975 850 L975 960 L1080 960 L1080 1200Z"/>
      </g>
      <g transform={`translate(540 1020) scale(${zoom}) translate(-540 -1020)`}>
        <Warrior frame={frame}/>
      </g>
      {particles.map((p,i)=><circle key={i} cx={(p.x+p.dx)%1080} cy={(p.y+p.dy+1920)%1920} r={p.r} fill="#f2c18a" opacity={0.12+(i%5)*0.07}/>)}
      <rect x="0" y="0" width="1080" height="1920" fill="none" stroke="#080f13" strokeWidth="80" opacity=".13"/>
    </svg>
  </AbsoluteFill>;
};
