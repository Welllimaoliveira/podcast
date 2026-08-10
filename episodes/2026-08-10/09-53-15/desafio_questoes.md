# DESAFIO PRF

Resolva as quatro questões antes de olhar o gabarito.

## Questão 1

PRF 2021 - CEBRASPE - Item 27

Considere um modelo em que a taxa de espalhamento de uma notícia seja p vezes (1 - p), com constante de proporcionalidade igual a 1. Se 30% da população já conhece a notícia, então a taxa de espalhamento é superior a 20% por unidade de tempo.

**Certo ou Errado?**

## Questão 2

PRF 2021 - CEBRASPE - Item 28

No modelo em que a taxa de espalhamento é p vezes (1 - p), se essa taxa for 16% por unidade de tempo, então necessariamente mais de 75% da população ainda desconhece a notícia.

**Certo ou Errado?**

## Questão 3

PRF 2021 - CEBRASPE - Item 29

No modelo de espalhamento dado por p vezes (1 - p), com p entre zero e um, é possível que a taxa de espalhamento de uma notícia ultrapasse 50% por unidade de tempo.

**Certo ou Errado?**

## Questão 4

PRF 2021 - CEBRASPE - Item 30

No mesmo modelo, quanto maior for o número de pessoas que já conhecem uma notícia, maior será necessariamente sua taxa de espalhamento.

**Certo ou Errado?**

---

# GABARITO

1. CERTO
2. ERRADO
3. ERRADO
4. ERRADO

# EXPLICAÇÕES

## Questão 1

Gabarito oficial: **CERTO**

A taxa de espalhamento é dada pela função f(p) = p * (1 - p), em que p representa a proporção de pessoas que já conhecem a notícia. Como 30% da população já conhece o fato, temos p = 0,30. Aplicando a fórmula do modelo, a taxa de espalhamento é calculada como 0,30 * (1 - 0,30) = 0,30 * 0,70 = 0,21, o que corresponde a 21% por unidade de tempo. Como 21% é estritamente superior a 20%, a afirmativa apresentada na questão está correta. A pegadinha consiste em confundir a porcentagem de pessoas que conhecem a notícia (30%) diretamente com a taxa final de espalhamento, sem aplicar o produto da fórmula f(p) = p * (1 - p). O candidato deveria realizar a simples substituição do valor na função para chegar ao valor exato de 21%.

## Questão 2

Gabarito oficial: **ERRADO**

A taxa de espalhamento é p * (1 - p) = 0,16. Resolvendo a equação do segundo grau p - p^2 = 0,16, temos p^2 - p + 0,16 = 0. As raízes dessa equação são p = 0,20 (20%) e p = 0,80 (80%). A porcentagem de pessoas que desconhecem a notícia é representada por 1 - p. Se p = 0,80, então 1 - p = 0,20 (20% da população desconhece a notícia). Por outro lado, se p = 0,20, temos 1 - p = 0,80 (80%). A afirmativa afirma que necessariamente mais de 75% desconhece a notícia, o que é falso, pois a porcentagem pode ser de apenas 20%. A pegadinha do item está no termo 'necessariamente', ignorando a segunda raiz válida da equação do segundo grau. O candidato deveria encontrar as duas possibilidades e constatar que uma delas desmente o enunciado.

## Questão 3

Gabarito oficial: **ERRADO**

A função de espalhamento f(p) = p * (1 - p) = -p^2 + p representa uma parábola com concavidade voltada para baixo. O ponto de máximo dessa função ocorre no vértice, calculado por p = -b / (2a) = -1 / (-2) = 0,50 (50%). Substituindo esse valor máximo na função, obtemos f(0,50) = 0,50 * 0,50 = 0,25, ou seja, a taxa máxima de espalhamento é de 25% por unidade de tempo. Assim, é impossível que a taxa ultrapasse 50%. A pegadinha da questão reside em tentar induzir o candidato a achar que, por p variar de 0 a 1, a taxa de espalhamento também poderia chegar a valores próximos de 100% ou ultrapassar 50%. O candidato precisava identificar o vértice da parábola para determinar o limite máximo de 25%.

## Questão 4

Gabarito oficial: **ERRADO**

A função f(p) = p * (1 - p) descreve um comportamento quadrático. A taxa de espalhamento cresce apenas no intervalo em que p varia de 0 a 0,50 (quando até 50% das pessoas conhecem a notícia), atingindo seu pico de 25%. A partir de p = 0,50 até p = 1,00, a taxa de espalhamento passa a diminuir, tendendo a zero quando todos já conhecem a notícia. Portanto, não é correto afirmar que quanto maior o número de pessoas que conhecem a notícia, maior será necessariamente a taxa. A pegadinha consiste na ideia intuitiva equivocada de que quanto mais pessoas sabem, mais rápido a informação se espalha indefinidamente. O candidato deveria analisar o comportamento do gráfico da parábola para perceber o decrescimento após o ponto médio.
