#ifndef RUNNER_UTILS_H_
#define RUNNER_UTILS_H_

#include <string>
#include <vector>

// Cria um console de depuração e direciona stdout/stderr para o processo Flutter.
void CreateAndAttachConsole();

// Converte texto UTF-16 para UTF-8 e retorna texto vazio quando a conversão falha.
std::string Utf8FromUtf16(const wchar_t* utf16_string);

// Lê os argumentos do processo em UTF-8, sem incluir o nome do executável.
std::vector<std::string> GetCommandLineArguments();

#endif  // RUNNER_UTILS_H_
