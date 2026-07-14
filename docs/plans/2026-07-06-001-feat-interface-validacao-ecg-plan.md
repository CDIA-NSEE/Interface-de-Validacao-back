---
title: Interface de Validacao de ECG - Plan
type: feat
date: 2026-07-06
topic: interface-validacao-ecg
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: ce-brainstorm
execution: code
---

# Interface de Validacao de ECG - Plan

## Goal Capsule

- **Objective:** Consolidar uma referencia mestre para entender o estado atual da Plataforma de Revisao de ECG e orientar a evolucao da interface ate o fluxo final de validacao medica.
- **Product authority:** Este documento registra as decisoes de produto e UX discutidas em 2026-07-06 e deve orientar planejamentos futuros antes de qualquer implementacao.
- **Open blockers:** A lista exata dia-para-diagnostico do ciclo fixo de 30 dias e o dominio institucional BP aceito no login ainda precisam ser definidos.

---

## Product Contract

### Summary

A interface deve apoiar medicos especialistas na validacao rapida e precisa de ECGs, com foco em reduzir atrito antes e durante a revisao.
O produto evoluira do fluxo atual baseado em status do exame para um ciclo global de validacao por diagnostico padronizado, com calendario fixo de 30 dias e revalidacao geral no dia 30.
Este documento descreve o estado atual, a experiencia desejada e as pendencias para que implementacoes futuras nao precisem inferir regras de produto.

### Problem Frame

O publico principal sao medicos de diferentes idades e niveis de familiaridade com tecnologia.
A interface precisa ser clara para quem tem dificuldade com leitura, telas densas ou fluxos digitais, mas tambem precisa preservar velocidade para especialistas que validarao muitos ECGs em sequencia.

O trabalho principal do medico nao e navegar pelo sistema, e sim validar diagnosticos de ECG a partir da imagem do exame e dos textos extraidos do PDF original.
Os exemplos de entrada ficam em `data/input`, os metadados extraidos ficam em `data/database/metadata.db`, e a proposta de agrupamento de mensagens similares aparece em `data/agrpuamentos`.

O sistema atual ja oferece login, home, fila de exames, tela de revisao e persistencia local, mas ainda nao possui o conceito central futuro de diagnostico do dia.
Hoje a unidade de progresso visivel e o exame; no fluxo alvo, a unidade operacional dos dias 1 a 29 passa a ser a validacao global de um diagnostico padronizado dentro de um exame e ciclo.

### Current State

- O front usa React + Vite e esta em `front/src`, com rotas para login, home e revisao de exame.
- O back usa FastAPI e SQLModel em `back/app`, com autenticacao por usuario/senha, endpoints de exames, diagnosticos, status e estatisticas.
- O banco de desenvolvimento usa SQLite por padrao e pode importar registros de `data/database/metadata.db`; quando nao ha metadados, a seed cria dados simulados.
- A tabela `metadata` guarda campos extraidos dos PDFs, incluindo texto, imagem, data do exame, sexo, idade, comentarios, conclusoes, notas, flags de extracao e erro.
- As conclusoes extraidas do metadata viram diagnosticos originais no sistema atual, e as opcoes de diagnostico sao derivadas das conclusoes disponiveis.
- A tela de login atual usa credenciais previamente cadastradas, sem cadastro publico, e ainda nao usa e-mail institucional BP como regra de entrada.
- A home atual mostra fila, busca, botao para iniciar revisao, resumo de validacao, filtros rapidos e ordenacao que prioriza exames em validacao.
- A tela de revisao atual mostra ECG, diagnosticos originais, diagnosticos adicionados pelo medico, dados clinicos, informacoes do laudo original, observacoes, status e acao de validar exame.
- O `docs/fluxograma-validacao-ecg.md` ja descreve o ciclo diario e o dia 30 como revalidacao geral, mas nao detalha as regras de fila global por diagnostico padronizado.

### Key Decisions

- **Documento mestre primeiro:** A proxima entrega e documentar produto e requisitos, nao implementar telas, dados ou infraestrutura.
- **Fila global por item:** Uma validacao de diagnostico conta globalmente para aquele item; depois que um medico valida um exame-diagnostico, ele sai da fila daquele diagnostico para todos.
- **Calendario fixo compartilhado:** O diagnostico do dia sera determinado por um calendario fixo de 30 dias, igual para todos os medicos.
- **Dia 30 fecha o ciclo:** O exame so deve ser considerado finalizado apos a revalidacao geral do dia 30.
- **Agrupamento versionado:** O Texto Padrao deve vir de uma fonte estruturada e versionada de agrupamentos, nao de texto livre gerado em tempo real.
- **IA como apoio:** A recomendacao da IA deve orientar e alertar, mas a decisao final continua manual e medica.
- **Home como fila do dia:** A home futura deve priorizar diagnostico do dia, quantidade pendente e acao de iniciar ou continuar validacao.
- **Validacao com painel esquerdo refinado:** A tela de validacao deve manter a estrutura atual como base, com painel de decisao a esquerda e ECG grande a direita.
- **Ajuda sem interromper:** Tutorial, contato e tema ficam na topbar; relatar problema fica como botao flutuante discreto de contato direto.

### Actors

- A1. **Medico validador:** Especialista responsavel por revisar ECGs e validar diagnosticos com rapidez e precisao.
- A2. **Administrador operacional:** Responsavel por convidar/cadastrar usuarios, manter regras operacionais e apoiar configuracoes futuras, sem ser o ator principal da validacao medica.
- A3. **Sistema de validacao:** Seleciona fila, aplica calendario do dia, preserva rastreabilidade entre texto original, texto padrao, exame e decisoes.
- A4. **IA de apoio:** Exibe recomendacoes auxiliares sem tomar decisoes automaticas ou substituir a avaliacao do medico.

### Requirements

**Authentication and roles**

- R1. O login medico deve ser feito por e-mail institucional BP associado a uma conta criada ou convidada pelo administrador.
- R2. O dominio exato aceito para e-mails BP deve ficar configuravel ou documentado antes da implementacao da autenticacao final.
- R3. O login administrativo deve existir como acesso operacional separado da rotina medica.
- R4. A tela de login deve incluir as logos NSEE e BP presentes em `icons` e uma composicao visual com cor de fundo institucional.
- R5. O sistema nao deve oferecer cadastro publico de novos medicos pela tela de login.

**Daily cycle and queue**

- R6. O sistema deve apresentar, em todo login medico, um pop-up inicial informando o diagnostico ativo do dia.
- R7. Enquanto o pop-up estiver aberto, o restante da home deve ficar visualmente despriorizado.
- R8. Depois do fechamento do pop-up, o diagnostico do dia deve permanecer visivel em uma area persistente da home e da validacao.
- R9. Nos dias 1 a 29, a fila deve selecionar apenas ECGs que possuam ao menos um diagnostico associado ao diagnostico padronizado do dia.
- R10. A fila dos dias 1 a 29 deve operar por validacao global de `exame + diagnostico padronizado + ciclo`.
- R11. Um ECG validado apenas para o diagnostico do dia pode reaparecer em outro dia quando possuir outro diagnostico pendente daquele novo dia.
- R12. No dia 30, todos os exames do ciclo devem entrar em revalidacao geral, mesmo os que nao tiveram divergencia nos dias anteriores.
- R13. O exame deve ser considerado finalizado somente apos a revalidacao geral do dia 30.

**Home experience**

- R14. A home deve priorizar a fila do dia, a quantidade de exames pendentes e uma acao principal para iniciar ou continuar validacao.
- R15. A home deve manter resumo de validacao, mas ele nao deve competir visualmente com a acao de validar.
- R16. O titulo "Resumo da validacao" deve ter fonte maior e hierarquia clara quando exibido.
- R17. A home deve ter topbar com icone ou marca, nome da pagina, relogio, usuario logado e acoes globais.
- R18. A topbar deve incluir tutorial rapido, contato direto e alternancia de tema.
- R19. O botao de relatar problema deve ficar sempre acessivel como controle flutuante discreto, sem cobrir informacoes clinicas.
- R20. O tutorial deve ser um guia rapido in-app com passos essenciais de validacao.
- R21. O contato direto deve informar canais de suporte BP/NSEE, sem criar sistema de tickets nesta fase.

**Review experience**

- R22. A tela de validacao deve destacar o diagnostico obrigatorio do dia em primeiro lugar no painel esquerdo.
- R23. O diagnostico do dia deve usar cor e hierarquia visual para diferenciar obrigatorio de opcional.
- R24. Cada diagnostico deve exibir `Texto Padrao` acima de `Texto Original`, preservando a rastreabilidade para o texto extraido.
- R25. O Texto Padrao deve vir do agrupamento canonico de mensagens equivalentes.
- R26. O Texto Original deve ser o texto extraido do arquivo original e persistido a partir do metadata.
- R27. O medico deve validar no minimo o diagnostico obrigatorio do dia para poder avancar.
- R28. Diagnosticos adicionais do mesmo ECG devem ser opcionais nos dias 1 a 29.
- R29. A acao principal apos salvar o diagnostico obrigatorio deve abrir automaticamente o proximo ECG da fila do dia.
- R30. Uma acao secundaria deve permitir permanecer no ECG atual para validar diagnosticos opcionais antes do autoavanco.
- R31. Quando o medico abrir um ECG que ja possui validacao anterior de um diagnostico, o sistema deve permitir editar essa decisao.
- R32. Uma decisao anterior ja registrada nao deve exigir que o medico clique novamente em concordar ou discordar para seguir, a menos que queira alterar.
- R33. O botao de concordar deve destacar o diagnostico em verde quando ativo e deixar discordar em tom neutro, ainda clicavel.
- R34. O botao de discordar deve destacar o diagnostico em vermelho quando ativo e deixar concordar em tom neutro, ainda clicavel.
- R35. A tela deve incluir uma area para recomendacao da IA, identificada como apoio nao decisivo.
- R36. O ECG exibido deve usar imagem real extraida do fluxo de dados quando disponivel, mantendo `front/public/sample-ecg.svg` apenas como fallback ou exemplo.
- R37. Dados clinicos e laudo original devem continuar disponiveis sem ocupar o foco principal da validacao.

**Accessibility and visual clarity**

- R38. A interface deve funcionar para medicos com baixa familiaridade digital, mantendo comandos principais visiveis, rotulos claros e estados de erro compreensiveis.
- R39. Pequenos subtextos cinza devem ser removidos sempre que forem redundantes ou secundarios.
- R40. Informacoes auxiliares ocultadas devem estar disponiveis por tooltip em hover, foco de teclado e toque.
- R41. Instrucoes criticas para concluir a tarefa nao devem depender apenas de tooltip.
- R42. O modo claro deve ser o padrao inicial.
- R43. O modo escuro deve ser uma alternancia persistente por usuario ou dispositivo.
- R44. Textos, botoes e indicadores devem ser dimensionados para leitura confortavel em desktop e telas menores.

**Data and governance**

- R45. Os agrupamentos de diagnostico devem existir como arquivo ou tabela estruturada versionada no projeto.
- R46. Cada agrupamento deve mapear uma ou mais frases originais para um Texto Padrao canonico.
- R47. A documentacao futura do banco deve distinguir o metadata extraido dos PDFs do banco operacional usado pela aplicacao.
- R48. A arquitetura AWS deve permanecer apenas como intencao futura neste documento, sem escolher servicos ou topologia.

### Key Flows

- F1. **Login medico diario**
  - **Trigger:** Medico acessa o sistema.
  - **Actors:** A1, A3.
  - **Steps:** O medico informa e-mail BP cadastrado e senha; o sistema valida a conta; a home abre com pop-up do diagnostico do dia; o medico confirma leitura e segue para a fila.
  - **Covered by:** R1, R2, R5, R6, R7, R8.

- F2. **Validacao rapida do diagnostico do dia**
  - **Trigger:** Medico inicia ou continua a fila do dia.
  - **Actors:** A1, A3, A4.
  - **Steps:** O sistema abre o proximo ECG elegivel; o painel esquerdo destaca o diagnostico obrigatorio; o medico compara ECG, Texto Padrao, Texto Original e apoio da IA; o medico concorda ou discorda; o sistema salva e avanca para o proximo ECG.
  - **Covered by:** R9, R22, R24, R27, R29, R35.

- F3. **Validacao opcional no mesmo ECG**
  - **Trigger:** O ECG aberto possui outros diagnosticos alem do diagnostico do dia.
  - **Actors:** A1, A3.
  - **Steps:** O medico valida o diagnostico obrigatorio; escolhe permanecer na tela; revisa diagnosticos opcionais; salva decisoes adicionais; avanca quando terminar.
  - **Covered by:** R28, R30, R31, R32.

- F4. **Reaparecimento em outro dia**
  - **Trigger:** Um ECG ja validado para um diagnostico possui outro diagnostico associado ao novo diagnostico do dia.
  - **Actors:** A1, A3.
  - **Steps:** O sistema inclui novamente o ECG na fila do novo dia; mostra decisoes anteriores quando relevantes; exige apenas a validacao pendente do diagnostico ativo.
  - **Covered by:** R10, R11, R31, R32.

- F5. **Revalidacao geral do dia 30**
  - **Trigger:** O ciclo chega ao dia 30.
  - **Actors:** A1, A3.
  - **Steps:** A home muda para modo de revalidacao geral; todos os exames do ciclo ficam disponiveis; o medico revisa resultados, diagnosticos adicionados e possiveis ajustes; o ciclo encerra quando todos forem revalidados.
  - **Covered by:** R12, R13.

### Acceptance Examples

- AE1. **Covers R6, R7, R8.** Given um medico faz login em um dia com diagnostico ativo, when a home carrega, then um pop-up informa esse diagnostico, a tela atras fica despriorizada e o diagnostico continua visivel depois do fechamento.
- AE2. **Covers R9, R10.** Given o diagnostico do dia e "Sobrecarga ventricular esquerda", when a fila e carregada, then aparecem apenas exames que possuam ao menos um diagnostico mapeado para esse Texto Padrao e ainda pendente no ciclo.
- AE3. **Covers R11.** Given um ECG tem dois diagnosticos padronizados e apenas um foi validado no dia anterior, when o outro diagnostico vira o diagnostico do dia, then o ECG pode reaparecer na fila.
- AE4. **Covers R24, R25, R26.** Given uma conclusao original "POSSIVEL SOBRECARGA VENTRICULAR ESQUERDA", when ela pertence ao agrupamento canonico, then a tela exibe o Texto Padrao do agrupamento acima do Texto Original extraido.
- AE5. **Covers R29, R30.** Given o medico validou o diagnostico obrigatorio, when aciona a acao principal, then o proximo ECG abre automaticamente; when escolhe a acao secundaria, then permanece no ECG para opcionais.
- AE6. **Covers R31, R32, R33, R34.** Given um diagnostico ja esta marcado como concordo, when o medico reabre o ECG, then a selecao verde aparece ativa e discordar permanece clicavel em estado neutro.
- AE7. **Covers R12, R13.** Given o ciclo esta no dia 30, when a home e aberta, then todos os exames do ciclo entram na lista de revalidacao e nenhum exame e considerado final antes dessa etapa.
- AE8. **Covers R39, R40, R41.** Given um texto auxiliar foi removido da tela, when o usuario passa mouse, foca por teclado ou toca no controle correspondente, then a informacao secundaria fica disponivel; instrucoes necessarias para concluir a validacao continuam visiveis.

### Scope Boundaries

**In scope for future planning**

- Refinar login medico/admin, home, validacao, tema, tutorial e contato direto.
- Modelar calendario fixo de 30 dias e progresso global por diagnostico padronizado.
- Formalizar agrupamentos como fonte estruturada versionada.
- Documentar melhor a relacao entre PDFs, metadata extraido, banco operacional e interface.

**Out of scope for this document**

- Implementar qualquer mudanca no front, back, banco, dados ou assets.
- Definir arquitetura AWS concreta.
- Criar sistema de tickets para relato de problemas.
- Liberar cadastro publico de medicos.
- Permitir que IA tome decisoes ou preencha concordo/discordo automaticamente.
- Fechar a lista exata de diagnosticos de cada dia sem insumo adicional.

### Dependencies and Assumptions

- A pasta `icons` contem `logo_BP.png` e `logo_NSEE.jpeg`, que devem ser usados no login futuro.
- A tabela `metadata` contem 20 registros no ambiente atual consultado em 2026-07-06.
- A pasta `data/agrpuamentos` contem imagens que exemplificam agrupamentos de frases originais em diagnosticos padronizados, mas a fonte final precisa ser estruturada para uso pelo sistema.
- O dominio institucional BP exato ainda nao foi definido.
- A tabela dia-para-diagnostico do ciclo fixo ainda nao foi fornecida.
- AWS deve ser tratado como trilha futura de infraestrutura, nao como requisito fechado deste documento.

### Success Criteria

- Um agente ou pessoa consegue entender o que o sistema faz hoje e o que precisa evoluir sem reabrir a conversa original.
- Um planejamento futuro consegue transformar este documento em tarefas de implementacao sem inventar regras de validacao, fila, atores ou escopo.
- O documento separa estado atual, proposta futura, limites de escopo e pendencias.
- A experiencia proposta prioriza velocidade de validacao sem esconder informacoes criticas para medicos com menor familiaridade tecnologica.

### Sources

- `README.md` para arquitetura atual, login de desenvolvimento, estados de exame e banco local.
- `docs/fluxograma-validacao-ecg.md` para o ciclo diario e revalidacao geral no dia 30.
- `front/src/pages/LoginPage.jsx` para a tela de login atual.
- `front/src/pages/DashboardPage.jsx` e `front/src/components/ValidationSummaryPanel.jsx` para a home atual.
- `front/src/pages/ExamReviewPage.jsx`, `front/src/components/DiagnosisPanel.jsx` e `front/src/components/EcgViewer.jsx` para a validacao atual.
- `back/app/main.py`, `back/app/models.py`, `back/app/seed.py` e `back/app/metadata_source.py` para API, modelos, importacao de metadata e diagnosticos.
- `data/database/metadata.db` para a fonte local de dados extraidos dos PDFs.
- `data/agrpuamentos` para exemplos visuais de agrupamento de conclusoes em diagnosticos padronizados.
- `icons` para marcas BP e NSEE.

### Outstanding Questions

**Resolve before implementation planning**

- Qual e o dominio exato aceito para e-mails institucionais BP?
- Qual e a tabela fixa dia-para-diagnostico dos dias 1 a 29?
- Qual formato estruturado deve representar os agrupamentos: arquivo versionado, tabela operacional ou ambos?
- Quais canais de contato BP/NSEE devem aparecer no botao de relatar problema?

**Deferred to implementation planning**

- Como migrar do status atual por exame para progresso por diagnostico sem perder revisoes existentes.
- Como armazenar ciclo, dia ativo, validacao global e revalidacao geral.
- Como servir imagens reais de ECG a partir dos dados importados, mantendo fallback seguro.
- Como persistir preferencia de tema por usuario ou dispositivo.
- Como tornar tooltips acessiveis em mouse, teclado e toque.
