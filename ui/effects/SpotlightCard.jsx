import React, { useRef, useState } from 'react';

export default function SpotlightCard({
  children,
  className = '',
  spotlightColor = 'rgba(215, 250, 103, 0.15)',
  borderColor = 'rgba(215, 250, 103, 0.4)',
  radius = 16,
  ...props
}) {
  const divRef = useRef(null);
  const [isFocused, setIsFocused] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e) => {
    if (!divRef.current || isFocused) return;
    const div = divRef.current;
    const rect = div.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleFocus = () => {
    setIsFocused(true);
    setOpacity(1);
  };

  const handleBlur = () => {
    setIsFocused(false);
    setOpacity(0);
  };

  const handleMouseEnter = () => {
    setOpacity(1);
  };

  const handleMouseLeave = () => {
    setOpacity(0);
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`spotlight-card ${className}`}
      style={{
        position: 'relative',
        borderRadius: `${radius}px`,
        overflow: 'hidden',
      }}
      {...props}
    >
      <div
        className="spotlight-overlay"
        style={{
          opacity,
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: 'none',
          transition: 'opacity 0.25s ease',
          background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 40%)`,
          zIndex: 1,
        }}
      />
      <div
        className="spotlight-border"
        style={{
          opacity,
          position: 'absolute',
          inset: 0,
          borderRadius: `${radius}px`,
          padding: '1px',
          mask: `radial-gradient(350px circle at ${position.x}px ${position.y}px, black, transparent 70%)`,
          WebkitMask: `radial-gradient(350px circle at ${position.x}px ${position.y}px, black, transparent 70%)`,
          pointerEvents: 'none',
          border: `1px solid ${borderColor}`,
          zIndex: 2,
        }}
      />
      <div style={{ position: 'relative', zIndex: 3 }}>
        {children}
      </div>
    </div>
  );
}
