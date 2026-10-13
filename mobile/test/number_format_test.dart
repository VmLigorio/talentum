// Talentum — mobile/test/number_format_test.dart
// Responsabilidade: Valida comportamentos importantes do aplicativo Flutter.
// Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/services.dart';

import 'package:talentum_mobile/main.dart';

/// Agrupa verificações de formatação numérica e máscara monetária do app.
void main() {
  // Confere agrupamento de milhares e precisão no padrão brasileiro.
  test('formata milhares, milhões e bilhões no padrão brasileiro', () {
    expect(formatBrazilianNumber(1000), '1.000,00');
    expect(formatBrazilianNumber(1000000), '1.000.000,00');
    expect(formatBrazilianNumber(1000000000), '1.000.000.000,00');
    expect(formatBrazilianNumber(1234.56), '1.234,56');
  });

  // Valida conversão de texto brasileiro para valores numéricos.
  test('interpreta valores digitados com ponto e vírgula brasileiros', () {
    expect(parseBrazilianNumber('1.000,00'), 1000);
    expect(parseBrazilianNumber('1.000.000,50'), 1000000.5);
    expect(parseBrazilianNumber('32,50'), 32.5);
  });

  // Garante que a máscara mantenha cursor e limite de duas casas decimais.
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

  // Confirma que cotas descartam zeros decimais sem perder precisão útil.
  test('formata cotas removendo zeros decimais finais', () {
    expect(formatInvestmentQuantity('47.00000000'), '47');
    expect(formatInvestmentQuantity('47.12500000'), '47,125');
    expect(formatInvestmentQuantity('47.12000000'), '47,12');
  });
}
