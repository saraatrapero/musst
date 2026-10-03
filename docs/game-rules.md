# Reglas de juego

La referencia normativa es el **Reglamento de la Federación Española de Mus (FEM)**.

Esta base implementa explícitamente:

- baraja española de 40 cartas;
- equivalencia de modalidad de **ocho reyes y ocho ases** (3->rey, 2->as);
- control de acciones legales por fase mediante `RulesEngine`.

Las validaciones de lances completos (grande/chica/pares/juego/punto, envites, órdagos, tanteo completo a 40) se desarrollan incrementalmente sobre esta base.
