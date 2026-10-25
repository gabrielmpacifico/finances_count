# Finanças — planejador local

Aplicação pessoal para registrar lançamentos e projetar o saldo futuro. Os dados são gravados em `finances_data/financas.db`, um banco SQLite criado automaticamente nessa pasta. O servidor só escuta em `127.0.0.1` (este computador) e não envia registros financeiros para serviços externos.

## Iniciar no Windows

1. Tenha Python 3 instalado. SQLite faz parte da biblioteca padrão do Python; não é necessário instalar banco de dados à parte nem pacotes Python.
2. Abra `start.bat`. O navegador abrirá em `http://127.0.0.1:8765`.
3. Para encerrar, feche a janela do terminal que iniciou o programa.

Se o comando `py` não estiver disponível, o script tenta iniciar usando `python`.

## Backup

Use **Fazer backup do banco** na barra lateral ou em Configurações para baixar uma cópia. Para restaurar, encerre o programa e substitua `finances_data/financas.db` pela cópia salva. Também é possível copiar o arquivo com o programa encerrado.

## Recursos

- Lançamentos realizados e previstos: entradas, saídas da conta e compras no cartão. A categoria Salário substitui a previsão mensal quando uma entrada salarial é registrada.
- Projeção mensal até 12 meses, salário e gasto diário padrão do cartão, com visão detalhada de dois meses anteriores e próximos dois.
- O salário configurado é uma previsão; ao registrar uma entrada com categoria **Salário**, o valor previsto deixa de ser usado naquele mês. O salário recebido no dia 30 compõe o saldo que financia as contas do mês seguinte.
- A aba **Fluxo mensal** reúne lançamentos, salário, contas, fatura, repasses e saldo projetado para dois meses anteriores e dois posteriores ao atual.
- Contas mensais da casa, registro do valor pago e acompanhamento dos repasses calculados pelo percentual configurado.
- Ciclos do cartão com início, fechamento, pagamento e saldo inicial por mês.
- Dia padrão de fechamento do cartão configurado para 28; a data pode ser corrigida diretamente na linha do ciclo.
- Tema escuro, com preferência salva neste navegador.
- Backup do banco SQLite e exclusão de registros.

## Notas de uso

- Informe o saldo atual da conta em **Configurações** para iniciar uma projeção coerente.
- Cadastre estimativas de contas nos meses futuros; os valores reais podem substituir as estimativas conforme forem conhecidos.
- O campo de parcelas é apenas informativo; inclua as parcelas futuras no saldo inicial dos ciclos correspondentes. Ciclos sem fechamento confirmado usam o dia de fechamento padrão configurado para estimar a fatura e mostram essa previsão separada dos gastos registrados.
- Marque **Prever nos meses seguintes** em uma conta para replicar seu valor nos cálculos dos meses futuros até que você altere a marcação. Dias passados sem compra de cartão registrada contam como R$ 0; os R$ 40 configurados são aplicados somente aos dias de hoje em diante que não tenham lançamento no cartão.
- Faça backups regulares e mantenha as cópias fora da pasta do programa. Esta versão fica disponível apenas neste computador.
