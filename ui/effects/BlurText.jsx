import React, { useEffect, useRef, useState } from 'react';

export default function BlurText({
  text = '',
  delay = 50,
  className = '',
  animateBy = 'words', // 'words' or 'letters'
  direction = 'top', // 'top' or 'bottom'
  onAnimationComplete,
}) {
  const elements = animateBy === 'words' ? text.split(' ') : text.split('');
  const [inView, setInView] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.unobserve(ref.current);
        }
      },
      { threshold: 0.1 }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <span ref={ref} className={`blur-text-wrapper ${className}`} style={{ display: 'inline-block' }}>
      {elements.map((segment, index) => (
        <span
          key={index}
          style={{
            display: 'inline-block',
            filter: inView ? 'blur(0px)' : 'blur(10px)',
            opacity: inView ? 1 : 0,
            transform: inView
              ? 'translate3d(0, 0, 0)'
              : `translate3d(0, ${direction === 'top' ? '-18px' : '18px'}, 0)`,
            transition: `all 0.5s cubic-bezier(0.2, 0.65, 0.3, 0.9) ${index * delay}ms`,
            marginRight: animateBy === 'words' ? '0.3em' : '0em',
            willChange: 'transform, filter, opacity',
          }}
        >
          {segment === ' ' ? '\u00A0' : segment}
        </span>
      ))}
    </span>
  );
}
