import React, { useEffect, useRef, useState } from 'react';

export default function CountUp({
  to = 100,
  from = 0,
  duration = 2,
  delay = 0,
  decimals = 0,
  separator = ',',
  prefix = '',
  suffix = '',
  className = '',
  ...props
}) {
  const [current, setCurrent] = useState(from);
  const elementRef = useRef(null);
  const startTimeRef = useRef(null);
  const hasAnimatedRef = useRef(false);

  useEffect(() => {
    let frameId;
    let timeoutId;

    const easeOutExpo = (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));

    const animate = (timestamp) => {
      if (!startTimeRef.current) startTimeRef.current = timestamp;
      const progress = Math.min((timestamp - startTimeRef.current) / (duration * 1000), 1);
      const eased = easeOutExpo(progress);
      const value = from + (to - from) * eased;
      setCurrent(value);

      if (progress < 1) {
        frameId = requestAnimationFrame(animate);
      } else {
        setCurrent(to);
      }
    };

    const start = () => {
      if (hasAnimatedRef.current) return;
      hasAnimatedRef.current = true;
      timeoutId = setTimeout(() => {
        frameId = requestAnimationFrame(animate);
      }, delay * 1000);
    };

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          start();
          observer.disconnect();
        }
      },
      { threshold: 0.1 }
    );

    if (elementRef.current) {
      observer.observe(elementRef.current);
    }

    return () => {
      observer.disconnect();
      clearTimeout(timeoutId);
      cancelAnimationFrame(frameId);
    };
  }, [to, from, duration, delay]);

  const formatted = (() => {
    const parts = current.toFixed(decimals).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, separator);
    return parts.join('.');
  })();

  return (
    <span ref={elementRef} className={`count-up ${className}`} {...props}>
      {prefix}{formatted}{suffix}
    </span>
  );
}
