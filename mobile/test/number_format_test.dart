// Talentum — mobile/test/number_format_test.dart
// Responsabilidade: Valida comportamentos importantes do aplicativo Flutter.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/services.dart';

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

  test('aplica máscara de milhares e permite no máximo duas casas decimais',
      () {
    const formatter = TwoDecimalMoneyInputFormatter();
    const empty = TextEditingValue(text: '');
    final grouped = formatter.formatEditUpdate(
      empty,
      const TextEditingValue(text: '1234'),
    );
    expect(grouped.text, '1.234');

    final withCents = formatter.formatEditUpdate(
      grouped,
      const TextEditingValue(text: '1234,56'),
    );
    expect(withCents.text, '1.234,56');

    final decimalEntry = formatter.formatEditUpdate(
      grouped,
      const TextEditingValue(
        text: '1234,',
        selection: TextSelection.collapsed(offset: 5),
      ),
    );
    expect(decimalEntry.text, '1.234,');
    expect(decimalEntry.selection.baseOffset, 6);

    final rejectedThirdDecimal = formatter.formatEditUpdate(
      withCents,
      const TextEditingValue(text: '1234,567'),
    );
    expect(rejectedThirdDecimal.text, '1.234,56');
  });

  test('formata cotas removendo zeros decimais finais', () {
    expect(formatInvestmentQuantity('47.00000000'), '47');
    expect(formatInvestmentQuantity('47.12500000'), '47,125');
    expect(formatInvestmentQuantity('47.12000000'), '47,12');
  });
}
