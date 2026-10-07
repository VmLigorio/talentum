// Talentum — mobile-react-native-prototype/src/money.ts
// Máscara e conversão de valores digitados no padrão brasileiro.

export function formatMoneyInput(input: string): string {
  const sanitized = input.replace(/[^\d,.-]/g, '');
  if (!sanitized || sanitized === '-') return sanitized;
  const commaIndex = sanitized.indexOf(',');
  const periodsAreGrouping = commaIndex < 0 && /^-?\d{1,3}(\.\d{3})+$/.test(sanitized);
  const separatorIndex = commaIndex >= 0
    ? commaIndex
    : periodsAreGrouping
      ? -1
      : sanitized.lastIndexOf('.');
  const integerSource = separatorIndex >= 0 ? sanitized.slice(0, separatorIndex) : sanitized;
  const fraction = separatorIndex >= 0
    ? sanitized.slice(separatorIndex + 1).replace(/\D/g, '').slice(0, 2)
    : '';
  const negative = integerSource.startsWith('-');
  const digits = integerSource.replace(/\D/g, '');
  const grouped = (digits || '0').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${negative ? '-' : ''}${grouped}${separatorIndex >= 0 ? `,${fraction}` : ''}`;
}

export function parseMoneyInput(input: string): number {
  const formatted = formatMoneyInput(input);
  if (!formatted || formatted === '-') return Number.NaN;
  const normalized = formatted.replace(/\./g, '').replace(',', '.');
  return Number(normalized);
}

export function formatInvestmentQuantity(value: number | string | null | undefined): string {
  if (value == null || value === '') return '0';
  const raw = typeof value === 'number'
    ? value.toLocaleString('en-US', { useGrouping: false, maximumFractionDigits: 8 })
    : value.trim().replace(',', '.');
  const normalized = /e/i.test(raw)
    ? Number(raw).toLocaleString('en-US', { useGrouping: false, maximumFractionDigits: 8 })
    : raw;
  const decimalIndex = normalized.indexOf('.');
  if (decimalIndex < 0) return normalized;
  const integer = normalized.slice(0, decimalIndex);
  const fraction = normalized.slice(decimalIndex + 1).replace(/0+$/, '');
  return fraction ? `${integer},${fraction}` : integer;
}

export function moneyCaretOffset(formatted: string, digitsBeforeCaret: number, pastDecimal = false): number {
  if (digitsBeforeCaret <= 0) return pastDecimal ? formatted.indexOf(',') + 1 : 0;
  let seen = 0;
  for (let index = 0; index < formatted.length; index += 1) {
    if (/\d/.test(formatted[index])) seen += 1;
    if (seen >= digitsBeforeCaret) {
      const offset = index + 1;
      const decimalIndex = formatted.indexOf(',');
      return pastDecimal && decimalIndex >= 0 ? Math.max(offset, decimalIndex + 1) : offset;
    }
  }
  return formatted.length;
}
