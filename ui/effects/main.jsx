import React from 'react';
import { createRoot } from 'react-dom/client';
import MicroSlats from './MicroSlats';
import TechText from './TechText';
import HoldButton from './HoldButton';

const roots = new Map();

function mount() {
  const slats = document.querySelector('[data-effect="micro-slats"]');
  if (slats && !roots.has(slats)) {
    const root = createRoot(slats);
    root.render(
      <MicroSlats
        preset="swell"
        color="#A855F7"
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

  const text = document.querySelector('[data-effect="tech-text"]');
  if (text && !roots.has(text)) {
    const root = createRoot(text);
    root.render(
      <TechText
        text="SWITCHBLADE"
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
    roots.set(text, root);
  }

  document.querySelectorAll('[data-decision]').forEach(button => {
    const host = document.createElement('span');
    host.className = 'hold-action';
    host.dataset.effect = 'hold-button';
    host.dataset.approved = String(button.dataset.decision === 'approve');
    host.dataset.escrow = button.dataset.escrow;
    host.dataset.ready = String(!button.disabled);
    button.replaceWith(host);
  });

  document.querySelectorAll('[data-effect="hold-button"]').forEach(element => {
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
        onHold={() => document.dispatchEvent(new CustomEvent('switchblade:decision', { detail: { escrowId, approved } }))}
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
      root.unmount();
      roots.delete(element);
    }
  }
});
document.addEventListener('switchblade:after-render', mount);
mount();
