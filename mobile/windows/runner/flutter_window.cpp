#include "flutter_window.h"

#include <optional>

#include "flutter/generated_plugin_registrant.h"

// Mantém o projeto Dart que será usado ao criar o controller da janela.
FlutterWindow::FlutterWindow(const flutter::DartProject& project)
    : project_(project) {}

// Libera o controller Flutter antes de a classe-base encerrar a janela.
FlutterWindow::~FlutterWindow() {}

// Cria o mecanismo Flutter, registra plugins e hospeda a visualização na janela.
bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  // Usa as dimensões da janela para evitar recriar a superfície durante a inicialização.
  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  // Interrompe a criação se o mecanismo ou a visualização não inicializou.
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  // Associa ao mecanismo os plugins necessários antes de montar a janela nativa.
  RegisterPlugins(flutter_controller_->engine());
  SetChildContent(flutter_controller_->view()->GetNativeWindow());

  // Exibe a janela somente depois que o Flutter concluir o primeiro quadro.
  flutter_controller_->engine()->SetNextFrameCallback([&]() {
    this->Show();
  });

  // Garante que a janela será exibida mesmo se o primeiro quadro terminar antes do callback.
  flutter_controller_->ForceRedraw();

  return true;
}

// Libera o controller Flutter e delega a destruição da janela à classe-base.
void FlutterWindow::OnDestroy() {
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

// Oferece as mensagens Win32 ao Flutter antes do processamento padrão da janela.
LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message,
                              WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  // Permite que o Flutter e seus plugins processem a mensagem primeiro.
  if (flutter_controller_) {
    std::optional<LRESULT> result =
        flutter_controller_->HandleTopLevelWindowProc(hwnd, message, wparam,
                                                      lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      // A mensagem pode chegar antes ou após o ciclo do controller.
      // Este acesso não repete a guarda acima (achado 149).
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}
