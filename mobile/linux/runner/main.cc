#include "my_application.h"

// Inicializa a aplicação GTK e encaminha os argumentos ao ciclo de vida do app.
int main(int argc, char** argv) {
  g_autoptr(MyApplication) app = my_application_new();
  return g_application_run(G_APPLICATION(app), argc, argv);
}
