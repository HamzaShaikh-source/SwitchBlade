import React, { useEffect, useState, useRef } from 'react';

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+~|}{[]:;?><,./-=';

export default function DecryptedText({
  text = '',
  speed = 45,
  maxIterations = 12,
  sequential = true,
  revealDirection = 'start',
  useOriginalCharsOnly = false,
  characters = LETTERS,
  className = '',
  parentClassName = '',
  encryptedClassName = 'decrypted-encrypted',
  animateOn = 'hover', // 'view' or 'hover'
  ...props
}) {
  const [displayText, setDisplayText] = useState(text);
  const [isHovering, setIsHovering] = useState(false);
  const [isScrambling, setIsScrambling] = useState(false);
  const [revealedIndices, setRevealedIndices] = useState(new Set());
  const containerRef = useRef(null);

  useEffect(() => {
    let interval;
    let currentIteration = 0;

    const getNextChar = (char) => {
      if (char === ' ') return ' ';
      if (useOriginalCharsOnly) {
        const unique = Array.from(new Set(text.replace(/\s/g, '')));
        return unique[Math.floor(Math.random() * unique.length)] || char;
      }
      return characters[Math.floor(Math.random() * characters.length)];
    };

    if (isHovering || animateOn === 'view') {
      setIsScrambling(true);
      interval = setInterval(() => {
        setDisplayText(() => {
          return text
            .split('')
            .map((char, index) => {
              if (char === ' ') return ' ';
              if (revealedIndices.has(index)) return text[index];
              return getNextChar(char);
            })
            .join('');
        });

        currentIteration++;

        if (sequential) {
          const nextIndex =
            revealDirection === 'end'
              ? text.length - 1 - revealedIndices.size
              : revealedIndices.size;
          if (nextIndex >= 0 && nextIndex < text.length) {
            setRevealedIndices((prev) => new Set([...prev, nextIndex]));
          }
        } else {
          setRevealedIndices((prev) => {
            const next = new Set(prev);
            const remaining = text
              .split('')
              .map((_, i) => i)
              .filter((i) => !prev.has(i));
            if (remaining.length > 0) {
              const randomIndex = remaining[Math.floor(Math.random() * remaining.length)];
              next.add(randomIndex);
            }
            return next;
          });
        }

        if (revealedIndices.size >= text.length || currentIteration > maxIterations + text.length) {
          setDisplayText(text);
          setIsScrambling(false);
          clearInterval(interval);
        }
      }, speed);
    } else {
      setDisplayText(text);
      setRevealedIndices(new Set());
      setIsScrambling(false);
    }

    return () => clearInterval(interval);
  }, [isHovering, text, speed, maxIterations, sequential, revealDirection, characters, useOriginalCharsOnly, animateOn, revealedIndices.size]);

  const handleMouseEnter = () => {
    if (animateOn === 'hover') {
      setRevealedIndices(new Set());
      setIsHovering(true);
    }
  };

  const handleMouseLeave = () => {
    if (animateOn === 'hover') {
      setIsHovering(false);
    }
  };

  return (
    <span
      ref={containerRef}
      className={`decrypted-text-container ${parentClassName}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      <span className={className}>
        {displayText.split('').map((char, i) => {
          const isRevealed = revealedIndices.has(i) || !isScrambling;
          return (
            <span
              key={i}
              className={isRevealed ? 'char-revealed' : encryptedClassName}
            >
              {char}
            </span>
          );
        })}
      </span>
    </span>
  );
}
