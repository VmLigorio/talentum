import 'package:flutter_test/flutter_test.dart';

import 'package:talentum_mobile/main.dart';

void main() {
  test('formata milhares, milhões e bilhões no padrão brasileiro', () {
    expect(formatBrazilianNumber(1000), '1.000,00');
    expect(formatBrazilianNumber(1000000), '1.000.000,00');
    expect(formatBrazilianNumber(1000000000), '1.000.000.000,00');
    expect(formatBrazilianNumber(1234.56), '1.234,56');
  });

  test('interpreta valores digitados com ponto e vírgula brasileiros', () {
    expect(parseBrazilianNumber('1.000,00'), 1000);
    expect(parseBrazilianNumber('1.000.000,50'), 1000000.5);
    expect(parseBrazilianNumber('32,50'), 32.5);
  });
}
