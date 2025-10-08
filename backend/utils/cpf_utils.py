"""
Módulo utilitário para validação e normalização de CPF.
Funções reutilizáveis e testáveis, com nomes claros e comentários críticos.
"""
import re

class CPFUtils:
    @staticmethod
    def normalize_cpf(cpf: str) -> str:
        """
        Remove caracteres não numéricos do CPF.
        Parâmetros:
            cpf (str): CPF em qualquer formato
        Retorno:
            str: CPF apenas com dígitos
        Exemplo: '123.456.789-09' -> '12345678909'
        """
        return re.sub(r'\D', '', cpf)

    @staticmethod
    def is_valid_cpf(cpf: str) -> bool:
        """
        Valida CPF pelo algoritmo dos dígitos verificadores.
        Parâmetros:
            cpf (str): CPF apenas com dígitos
        Retorno:
            bool: True se válido, False caso contrário
        """
        cpf = CPFUtils.normalize_cpf(cpf)
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False
        # Cálculo dos dígitos verificadores
        for i in [9, 10]:
            soma = sum(int(cpf[j]) * ((i + 1) - j) for j in range(i))
            digito = ((soma * 10) % 11) % 10
            if int(cpf[i]) != digito:
                return False
        return True
