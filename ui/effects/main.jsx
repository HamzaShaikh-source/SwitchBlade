import React from 'react';
import { createRoot } from 'react-dom/client';
import MicroSlats from './MicroSlats';
import TechText from './TechText';
import HoldButton from './HoldButton';
import DecryptedText from './DecryptedText';
import SpotlightCard from './SpotlightCard';
import CountUp from './CountUp';
import Particles from './Particles';
import BlurText from './BlurText';

const roots = new Map();

function mount() {
  // 1. MicroSlats
  document.querySelectorAll('[data-effect="micro-slats"]').forEach((slats) => {
    if (!roots.has(slats)) {
      const root = createRoot(slats);
      root.render(
        <MicroSlats
          preset={slats.dataset.preset || 'swell'}
          color={slats.dataset.color || '#A855F7'}
          glintColor="#ffffff"
          backgroundColor="#000000"
          slatWidth={10}
          slatHeight={25}
          gap={3}
          roundness={0.75}
          interactive
          cursorStrength={1}
          cursorSize={40}
          swirl={0}
          trail={1.4}
          lean={0}
          intro
        />
      );
      roots.set(slats, root);
    }
  });

  // 2. TechText
  document.querySelectorAll('[data-effect="tech-text"]').forEach((textEl) => {
    if (!roots.has(textEl)) {
      const root = createRoot(textEl);
      const textVal = textEl.dataset.text || 'SWITCHBLADE';
      root.render(
        <TechText
          text={textVal}
          fontWeight={600}
          fontSize={150}
          reveal="letter"
          dashLength={4}
          dashGap={2}
          specks={15}
          intro="none"
          introDuration={2}
          clickKick
          guides={false}
        />
      );
      roots.set(textEl, root);
    }
  });

  // 3. Particles
  document.querySelectorAll('[data-effect="particles"]').forEach((partEl) => {
    if (!roots.has(partEl)) {
      const root = createRoot(partEl);
      root.render(
        <Particles
          particleCount={parseInt(partEl.dataset.count || '45', 10)}
          speed={parseFloat(partEl.dataset.speed || '0.35')}
          particleColors={['#d7fa67', '#06b6d4', '#ffffff', '#a855f7']}
          alpha={0.4}
        />
      );
      roots.set(partEl, root);
    }
  });

  // 4. DecryptedText
  document.querySelectorAll('[data-effect="decrypted-text"]').forEach((el) => {
    if (!roots.has(el)) {
      const text = el.dataset.text || el.textContent.trim();
      const speed = parseInt(el.dataset.speed || '40', 10);
      const animateOn = el.dataset.animateOn || 'hover';
      const root = createRoot(el);
      root.render(
        <DecryptedText
          text={text}
          speed={speed}
          animateOn={animateOn}
          className="decrypted-main"
          encryptedClassName="decrypted-encrypted"
        />
      );
      roots.set(el, root);
    }
  });

  // 5. CountUp
  document.querySelectorAll('[data-effect="count-up"]').forEach((el) => {
    if (!roots.has(el)) {
      const toVal = parseFloat(el.dataset.to || '0');
      const fromVal = parseFloat(el.dataset.from || '0');
      const durationVal = parseFloat(el.dataset.duration || '2.2');
      const decimalsVal = parseInt(el.dataset.decimals || '0', 10);
      const prefixVal = el.dataset.prefix || '';
      const suffixVal = el.dataset.suffix || '';
      const root = createRoot(el);
      root.render(
        <CountUp
          to={toVal}
          from={fromVal}
          duration={durationVal}
          decimals={decimalsVal}
          prefix={prefixVal}
          suffix={suffixVal}
        />
      );
      roots.set(el, root);
    }
  });

  // 6. BlurText
  document.querySelectorAll('[data-effect="blur-text"]').forEach((el) => {
    if (!roots.has(el)) {
      const text = el.dataset.text || el.textContent.trim();
      const delay = parseInt(el.dataset.delay || '40', 10);
      const animateBy = el.dataset.animateBy || 'words';
      const root = createRoot(el);
      root.render(
        <BlurText
          text={text}
          delay={delay}
          animateBy={animateBy}
          className="blur-text-inline"
        />
      );
      roots.set(el, root);
    }
  });

  // 7. SpotlightCard
  document.querySelectorAll('[data-effect="spotlight-card"]').forEach((el) => {
    if (!roots.has(el)) {
      const innerHTML = el.innerHTML;
      const spotlight = el.dataset.spotlight || 'rgba(215, 250, 103, 0.12)';
      const border = el.dataset.border || 'rgba(215, 250, 103, 0.35)';
      const radius = parseInt(el.dataset.radius || '8', 10);
      const root = createRoot(el);
      root.render(
        <SpotlightCard spotlightColor={spotlight} borderColor={border} radius={radius}>
          <div dangerouslySetInnerHTML={{ __html: innerHTML }} />
        </SpotlightCard>
      );
      roots.set(el, root);
    }
  });

  // 8. HoldButton decisions
  document.querySelectorAll('[data-decision]').forEach((button) => {
    const host = document.createElement('span');
    host.className = 'hold-action';
    host.dataset.effect = 'hold-button';
    host.dataset.approved = String(button.dataset.decision === 'approve');
    host.dataset.escrow = button.dataset.escrow;
    host.dataset.ready = String(!button.disabled);
    button.replaceWith(host);
  });

  document.querySelectorAll('[data-effect="hold-button"]').forEach((element) => {
    if (roots.has(element)) return;
    const approved = element.dataset.approved === 'true';
    const escrowId = element.dataset.escrow;
    const root = createRoot(element);
    root.render(
      <HoldButton
        size="md"
        radius={2}
        fillDirection="right"
        backgroundColor={approved ? '#242723' : '#aa442f'}
        fillColor={approved ? '#d7fa67' : '#f5b9a7'}
        textColor="#f1efe8"
        fillTextColor="#242723"
        holdTime={2000}
        disabled={approved && element.dataset.ready !== 'true'}
        doneLabel="Submitting…"
        onHold={() =>
          document.dispatchEvent(
            new CustomEvent('switchblade:decision', {
              detail: { escrowId, approved },
            })
          )
        }
      >
        {approved ? 'Hold to approve' : 'Hold to reject'}
      </HoldButton>
    );
    roots.set(element, root);
  });
}

document.addEventListener('switchblade:before-render', () => {
  for (const [element, root] of roots) {
    if (!element.isConnected || element.closest('#content')) {
      try {
        root.unmount();
      } catch (e) {}
      roots.delete(element);
    }
  }
});
document.addEventListener('switchblade:after-render', mount);
mount();
