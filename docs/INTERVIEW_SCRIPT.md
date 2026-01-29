# 🎤 Roteiro de Apresentação: MR. HEALTH Data Platform

Este roteiro foi estruturado para uma apresentação de **10 a 15 minutos**, focando em transformar requisitos técnicos em valor de negócio, exatamente como a DataLakers espera.

---

## 1. Abertura: O Desafio (2 min)
*   **Gancho Inicial:** "O projeto MR. HEALTH não era apenas um desafio de engenharia de dados, mas um desafio de escalabilidade de um sonho. O João Silva (CEO) precisava sair do 'sentimento' e ir para o 'dado' para expandir sua rede de 50 unidades."
*   **O Problema:** "O Ricardo (Operações) gastava 6 horas por dia consolidando 100 planilhas CSV manualmente. Isso gerava um delay de 3 dias para a tomada de decisão e uma margem de erro perigosa."
*   **Objetivo:** "Minha missão foi construir uma base sólida, capaz de processar tudo em menos de 3 minutos, com custo zero de infraestrutura e pronta para escalar para 500 lojas."

## 2. A Estratégia: Por que GCP e Serverless? (3 min)
*   **Escolha Tecnológica:** "Optei pelo Google Cloud Platform pela robustez do ecossistema de dados e pela facilidade de manter um MVP no **Free Tier** sem comprometer a arquitetura final."
*   **Arquitetura Orientada a Eventos:** "Nada de processos agendados (crons). Assim que a unidade faz o upload do CSV no **Cloud Storage**, uma **Cloud Function** é disparada na hora. Isso garante que o dado esteja disponível quase em tempo real."
*   **Camadas Medallion:** "Implementei a arquitetura de medalhões (Bronze, Silver, Gold).
    *   **Bronze:** Mantemos a verdade absoluta do dado bruto.
    *   **Silver:** Limpeza e normalização (onde eliminamos os erros manuais).
    *   **Gold:** Onde a mágica acontece com o **Star Schema** (Modelo Kimball), facilitando a vida do pessoal de BI."

## 3. O Diferencial: Desenvolvimento Agentic (3 min) - *Destaque aqui!*
*   **A "Máquina":** "Um ponto que orgulho muito neste projeto não é só o código, mas **como** ele foi feito. Utilizei uma infraestrutura de **Desenvolvimento Agentic** (Claude Code)."
*   **Eficiência:** "Construí esse ecossistema completo em cerca de **8 horas**. Projetos desse porte costumam levar 4 a 6 semanas. Usei 40 agentes especializados (Engenheiros de Dados, Revisores de Código, Arquitetos) para garantir que cada linha de código seguisse as melhores práticas."
*   **Qualidade:** "Isso me permitiu atingir **97.2% de cobertura de testes unitários**, algo raro em MVPs rápidos."

## 4. Resultados e Valor de Negócio (2 min)
*   **Impacto no Ricardo (COO):** "Liberamos a equipe dele de tarefas manuais. Agora eles analisam tendências de produtos e performance por estado (RS, SC, PR) em vez de copiar e colar células."
*   **Impacto no João (CEO):** "Ele agora tem o dashboard que desejava, com alertas automáticos e visibilidade total da receita e estoque."
*   **Custo:** "Operamos com **$0,00/mês**. Mostramos que é possível ter tecnologia de ponta sem gastar o orçamento de expansão da empresa."

## 5. Fechamento e Visão de Futuro (2 min)
*   **O que vem depois:** "A arquitetura que desenhei permite que, amanhã, possamos plugar modelos de **Machine Learning** para previsão de estoque (Demanda Predictiva) sem precisar mudar uma linha da nossa ingestão."
*   **Conclusão:** "Este projeto prova que, com a união de Engenharia de Dados moderna e IA, conseguimos entregar soluções de nível 'Enterprise' com agilidade extrema."

---

## 💡 Dicas de Ouro para a Entrevista:
1.  **Mencione os nomes:** João Silva, Ricardo e Wilson Luiz. Isso mostra que você leu o case e se importa com as pessoas do negócio.
2.  **Abra o HTML:** Quando falar da arquitetura, mostre os diagramas Mermaid que estão no portfólio. Eles são visualmente impactantes.
3.  **Fale de Testes:** Engenheiros de Dados que amam testes (97.2%!) são os favoritos das empresas.
4.  **Seja Proativo:** Se eles perguntarem sobre o PostgreSQL, diga: "Integramos as tabelas de Produto e Unidade como dimensões essenciais para cruzar com as vendas."
