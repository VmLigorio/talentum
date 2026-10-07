const test = require('node:test');
const assert = require('node:assert/strict');
const { harness } = require('./helpers.cjs');

const { formatMoneyInput, parseMoneyInput, moneyCaretOffset, formatInvestmentQuantity } = harness(() => {});

test('formats Brazilian thousands and decimal separators', () => {
  assert.equal(formatMoneyInput('1234567,89'), '1.234.567,89');
  assert.equal(formatMoneyInput('1234'), '1.234');
  assert.equal(formatMoneyInput('32.5'), '32,5');
});

test('limits fractional values to two digits and parses grouped values', () => {
  assert.equal(formatMoneyInput('123,4567'), '123,45');
  assert.equal(parseMoneyInput('1.234,56'), 1234.56);
  assert.equal(parseMoneyInput(''), Number.NaN);
});

test('maps caret after a grouping separator is inserted', () => {
  assert.equal(moneyCaretOffset('1.234', 4), 5);
  assert.equal(moneyCaretOffset('1.234,', 4, true), 6);
});

test('formats investment quotas and removes insignificant trailing zeros', () => {
  assert.equal(formatInvestmentQuantity('47.00000000'), '47');
  assert.equal(formatInvestmentQuantity('47.12500000'), '47,125');
  assert.equal(formatInvestmentQuantity(47.12), '47,12');
});
