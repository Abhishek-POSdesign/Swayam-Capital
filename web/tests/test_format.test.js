import { describe, it, expect } from 'vitest';
import { formatINR, formatNumber, formatPercent } from '../src/utils/format.js';

describe('Format Utilities', () => {
  it('formats positive INR amounts correctly', () => {
    expect(formatINR(11250)).toBe('₹11,250');
    expect(formatINR(850000)).toBe('₹8,50,000');
  });

  it('formats negative INR amounts correctly', () => {
    expect(formatINR(-11250)).toBe('-₹11,250');
  });

  it('formats percentages correctly', () => {
    expect(formatPercent(0.01)).toBe('1.0%');
    expect(formatPercent(0.025)).toBe('2.5%');
  });

  it('handles zero and nulls safely', () => {
    expect(formatINR(0)).toBe('₹0');
    expect(formatINR(null)).toBe('₹0');
    expect(formatPercent(null)).toBe('0.0%');
  });
});
