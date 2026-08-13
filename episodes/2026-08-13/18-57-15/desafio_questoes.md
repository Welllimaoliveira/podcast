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

Para resolver este item, basta substituir a proporção informada na função da taxa de espalhamento expressa por f(p) = p * (1 - p). Se 30% da população já conhece a notícia, a variável p assume o valor 0,30. Aplicando diretamente na fórmula: Taxa = 0,30 * (1 - 0,30) = 0,30 * 0,70 = 0,21, o que equivale a 21% por unidade de tempo. Como o resultado de 21% é estritamente superior ao valor de 20% indicado no enunciado, a afirmativa é verdadeira. A pegadinha para o candidato consistia em hesitar na modelagem ou errar o cálculo básico com números decimais, quando na verdade tratava-se de simples valor numérico de uma função quadrática. Gabarito: CERTO.

## Questão 2

Gabarito oficial: **ERRADO**

A questão propõe que uma taxa de 16% (0,16) implica necessariamente que mais de 75% desconhece a notícia. Montando a equação p * (1 - p) = 0,16, temos p² - p + 0,16 = 0. Resolvendo por Bhaskara, encontramos duas raízes reais válidas: p = 0,20 ou p = 0,80. A proporção dos que desconhecem a notícia é (1 - p). Se p = 0,20, a parcela desinformada é 80% (maior que 75%). Contudo, se p = 0,80, a parcela desinformada é de apenas 20% (menor que 75%). A pegadinha está no uso da palavra 'necessariamente', que desconsidera a segunda raiz real da equação quadrática. Logo, a afirmativa é incorreta. Gabarito: ERRADO.

## Questão 3

Gabarito oficial: **ERRADO**

A função da taxa de espalhamento é f(p) = -p² + p, caracterizada por uma parábola com concavidade voltada para baixo. O ponto em que a taxa atinge seu ápice é o vértice da parábola, dado por p = -b / (2a) = -1 / (2 * (-1)) = 0,5 (ou seja, quando 50% conhece a notícia). Substituindo esse valor na função, obtemos a taxa máxima: f(0,5) = 0,5 * (1 - 0,5) = 0,25 (25%). Portanto, a taxa máxima possível no modelo é de 25%, sendo impossível ultrapassar 50%. A pegadinha clássica da banca foi induzir o candidato a confundir o ponto de máximo (p = 0,50) com o valor máximo da taxa resultante. Gabarito: ERRADO.

## Questão 4

Gabarito oficial: **ERRADO**

A taxa de espalhamento f(p) = p * (1 - p) descreve uma curva quadrática e não uma relação linear monótona crescente. Para valores de p entre 0 e 0,5 (até 50%), a taxa de fato aumenta conforme mais pessoas conhecem a notícia, atingindo o máximo de 25%. Porém, a partir de p > 0,5, a taxa passa a decrescer progressivamente até atingir zero quando p = 1, pois restam cada vez menos pessoas suscetíveis a receber a notícia. A pegadinha reside no senso comum de achar que mais propagadores geram sempre maior ritmo de disseminação, ignorando o efeito do esgotamento do público-alvo na modelagem matemática. Gabarito: ERRADO.
