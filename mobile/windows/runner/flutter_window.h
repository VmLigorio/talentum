#ifndef RUNNER_FLUTTER_WINDOW_H_
#define RUNNER_FLUTTER_WINDOW_H_

#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>

#include <memory>

#include "win32_window.h"

// Janela Win32 responsável por hospedar uma visualização Flutter.
class FlutterWindow : public Win32Window {
 public:
  // Cria a janela e mantém o projeto Flutter que será executado nela.
  explicit FlutterWindow(const flutter::DartProject& project);
  // Libera a instância da janela Flutter.
  virtual ~FlutterWindow();

 protected:
  // Inicializa o controller Flutter e conecta a visualização à janela Win32.
  bool OnCreate() override;
  // Libera o controller Flutter antes de destruir a janela hospedeira.
  void OnDestroy() override;
  // Encaminha primeiro ao Flutter as mensagens Win32 relevantes para a interface.
  LRESULT MessageHandler(HWND window, UINT const message, WPARAM const wparam,
                         LPARAM const lparam) noexcept override;

 private:
  // Projeto Dart executado pelo controller da janela.
  flutter::DartProject project_;

  // Controller responsável pelo mecanismo e pela visualização Flutter.
  std::unique_ptr<flutter::FlutterViewController> flutter_controller_;
};

#endif  // RUNNER_FLUTTER_WINDOW_H_
