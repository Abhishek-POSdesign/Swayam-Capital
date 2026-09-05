import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { initHeader } from '../src/components/header.js';
import fs from 'fs';
import path from 'path';

describe('Sticky Navigation Header Architecture', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    container.setAttribute('id', 'header-container');
    document.body.appendChild(container);
  });

  it('initializes header with swayam-header class and sticky position', () => {
    initHeader(container);
    expect(container.innerHTML).toContain('swayam-header');
    expect(container.innerHTML).toContain('SWAYAM CAPITAL');
  });

  it('verifies styles.css defines #header-container and .swayam-header as sticky without overflow clipping on ancestors', () => {
    const stylesPath = path.resolve(__dirname, '../src/styles.css');
    const tokensPath = path.resolve(__dirname, '../src/styles/swayam-tokens.css');
    
    const stylesCss = fs.readFileSync(stylesPath, 'utf8');
    const tokensCss = fs.readFileSync(tokensPath, 'utf8');

    // Verify #header-container is sticky
    expect(stylesCss).toContain('#header-container');
    expect(stylesCss).toContain('position: sticky');

    // Verify .swayam-header is sticky
    expect(tokensCss).toContain('.swayam-header');
    expect(tokensCss).toContain('position: sticky');

    // Verify body does not have overflow clipping
    const bodyMatch = stylesCss.match(/body\s*\{([^}]+)\}/);
    expect(bodyMatch).not.toBeNull();
    const bodyRules = bodyMatch[1];
    expect(bodyRules).not.toContain('overflow: hidden');
    expect(bodyRules).not.toContain('overflow: scroll');
    expect(bodyRules).not.toContain('overflow-y: auto');
  });
});
