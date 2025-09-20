# TripLedger

💼 **TripLedger** é um sistema de gestão de caixa para colaboradores em viagem, desenvolvido em **Python + Streamlit**, com banco em **SQLite**.  
O objetivo foi praticar desenvolvimento de aplicações web, dashboards interativos e manipulação de dados financeiros em tempo real.

---

## ✨ Funcionalidades

### Para o colaborador
- Registrar transações de **entradas e saídas de caixa** (café da manhã, almoço, janta, Outros Serviços, Entrada e Saída de Caixa.);
- Informar **valor, descrição (Opcional), data e hora**;
- Anexar **foto do comprovante/cupom**;
- Visualizar o **saldo atualizado** em tempo real.

### Para o supervisor
- Painel consolidado do caixa de todos os colaboradores;
- **Dashboard principal** com:
  - Total de transações;
  - Valor total consumido;
  - Ticket médio;
  - Quantidade de usuários ativos;
- Gráficos de acompanhamento:
  - Transações por dia;
  - Distribuição de custos por tipo (pizza);
  - Ranking de usuários por valor consumido;
- Consulta detalhada por colaborador, com resumo financeiro (entradas, saídas, saldo total, dentre outras informações.);
- Exportação de relatórios detalhado em **CSV**.

---

## 🛠️ Tecnologias utilizadas
- [Python](https://www.python.org/)  
- [Streamlit](https://streamlit.io/)  
- [SQLite](https://www.sqlite.org/)  
- [Plotly](https://plotly.com/)  
- [Pillow](https://pillow.readthedocs.io/)

---

## 🚀 Como executar localmente

1. Clone este repositório:
   ```bash
   git clone https://github.com/aguinirpretti/TripLedger.git
   cd TripLedger
