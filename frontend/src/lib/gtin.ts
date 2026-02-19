export function computeGTINCheckDigit(payload: string): string {
  let sum = 0;
  const reversed = payload.split('').reverse();
  for (let i = 0; i < reversed.length; i += 1) {
    const digit = Number(reversed[i]);
    sum += digit * (i % 2 === 0 ? 3 : 1);
  }
  return String((10 - (sum % 10)) % 10);
}

export function validateGTIN(gtin: string): boolean {
  const digits = gtin.replace(/\D/g, '');
  if (![8, 12, 13, 14].includes(digits.length)) return false;
  const payload = digits.slice(0, -1);
  return digits.slice(-1) === computeGTINCheckDigit(payload);
}
