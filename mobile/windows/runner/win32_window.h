#ifndef RUNNER_WIN32_WINDOW_H_
#define RUNNER_WIN32_WINDOW_H_

#include <windows.h>

#include <functional>
#include <memory>
#include <string>

// Abstrai uma janela Win32 com suporte a escala DPI para subclasses Flutter.
class Win32Window {
 public:
  // Representa uma posição em pixels da tela.
  struct Point {
    unsigned int x;
    unsigned int y;
    Point(unsigned int x, unsigned int y) : x(x), y(y) {}
  };

  // Representa largura e altura da janela em pixels.
  struct Size {
    unsigned int width;
    unsigned int height;
    Size(unsigned int width, unsigned int height)
        : width(width), height(height) {}
  };

  // Inicializa o estado da janela e contabiliza a nova instância.
  Win32Window();
  // Destrói a janela e libera os recursos associados.
  virtual ~Win32Window();

  // Cria uma janela com título, posição e dimensões ajustadas ao DPI do monitor.
  // A janela permanece oculta até Show e retorna falso se a criação falhar.
  bool Create(const std::wstring& title, const Point& origin, const Size& size);

  // Exibe a janela criada e informa se ela já estava visível antes da chamada.
  bool Show();

  // Chama os hooks da subclasse e libera os recursos da janela Win32.
  void Destroy();

  // Insere o conteúdo nativo como filho e ajusta-o à área cliente da janela.
  void SetChildContent(HWND content);

  // Retorna o identificador Win32 da janela ou nulo após sua destruição.
  HWND GetHandle();

  // Define se fechar esta janela encerra o loop principal da aplicação.
  void SetQuitOnClose(bool quit_on_close);

  // Retorna os limites atuais da área interna da janela.
  RECT GetClientArea();

 protected:
  // Trata mensagens Win32 e permite que subclasses personalizem o processamento.
  virtual LRESULT MessageHandler(HWND window,
                                 UINT const message,
                                 WPARAM const wparam,
                                 LPARAM const lparam) noexcept;

  // Hook de inicialização chamado durante Create; a subclasse pode indicar falha.
  virtual bool OnCreate();

  // Hook executado antes da liberação da janela para limpar recursos da subclasse.
  virtual void OnDestroy();

 private:
  friend class WindowClassRegistrar;

  // Associa a instância à janela durante WM_NCCREATE e encaminha mensagens ao handler.
  static LRESULT CALLBACK WndProc(HWND const window,
                                  UINT const message,
                                  WPARAM const wparam,
                                  LPARAM const lparam) noexcept;

  // Recupera a instância C++ associada ao identificador Win32 informado.
  static Win32Window* GetThisFromHandle(HWND const window) noexcept;

  // Atualiza a decoração da janela de acordo com a preferência do sistema.
  static void UpdateTheme(HWND const window);

  bool quit_on_close_ = false;

  // Identificador da janela de nível superior.
  HWND window_handle_ = nullptr;

  // Identificador do conteúdo Flutter hospedado.
  HWND child_content_ = nullptr;
};

#endif  // RUNNER_WIN32_WINDOW_H_
