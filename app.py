import streamlit as st
from datetime import datetime
import os
import time
import uuid
import pandas as pd
import locale
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import sqlite3
import shutil
from PIL import Image
import io

# Configurar o modo wide
st.set_page_config(layout="wide", page_title="Gestão Financeira - Programa Zelar")

# Adicionar CSS personalizado para o rodapé
st.markdown("""
<style>
.footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    color: #888888;
    font-size: 10px;
    text-align: right;
    padding-right: 20px;
    padding-bottom: 5px;
    opacity: 0.7;
}
</style>
""", unsafe_allow_html=True)

# Configure o locale para o Brasil
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        pass  # Se não conseguir configurar o locale, usará o padrão

# Função para converter string para float aceitando vírgula ou ponto
def converter_para_float(valor_str):

    # Se já for número, apenas converte
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    
    # Se for vazio ou None
    if not valor_str:
        return 0.0
    
    # Garantir que seja string para manipulação
    valor_str = str(valor_str).strip()
    
    # Verificar se é um número inteiro sem casa decimal
    if valor_str.isdigit():
        return float(valor_str)
    
    try:
        # Tenta converter diretamente (assumindo formato americano)
        try:
            return float(valor_str)
        except:
            pass
            
        # Se falhou a conversão direta, tenta formatos especiais
        
        # Formato brasileiro: 45,70
        if ',' in valor_str and not '.' in valor_str:
            # Substitui vírgula por ponto para conversão
            return float(valor_str.replace(',', '.'))
            
        # Formato misto com separador de milhares e decimal: 1.234,56
        elif ',' in valor_str and '.' in valor_str and valor_str.find('.') < valor_str.find(','):
            # Remove pontos e substitui vírgula por ponto
            return float(valor_str.replace('.', '').replace(',', '.'))
            
        # Formato americano com separador de milhares: 1,234.56
        elif ',' in valor_str and '.' in valor_str and valor_str.find(',') < valor_str.find('.'):
            # Remove vírgulas
            return float(valor_str.replace(',', ''))
            
        # Último recurso: tenta remover todos os caracteres especiais
        return float(''.join(c for c in valor_str if c.isdigit() or c == '.'))
            
    except Exception as e:
        # Se tudo falhar, retorna zero
        return 0.0

# Função para obter o valor numérico de maneira segura
def obter_valor_numerico(valor):
    if isinstance(valor, (int, float)):
        return float(valor)
    
    try:
        # Se for string vazia, retorna 0
        if not valor or valor.strip() == '':
            return 0.0
            
        # Se for string, tenta converter para decimal
        return converter_para_float(valor)
    except:
        return 0.0

# Função para formatar valores para exibição no formato brasileiro
def formatar_valor(valor):
    try:
        # Converte para número primeiro
        valor_numerico = obter_valor_numerico(valor)
        
        # Garante que seja formatado com duas casas decimais
        return f"R$ {valor_numerico:.2f}".replace('.', ',')
    except:
        return "R$ 0,00"

# Rodapé
def adicionar_rodape():
    st.markdown(
        '<div class="footer">© 2025 • Aguinir Pretti</div>',
        unsafe_allow_html=True
    )

# Função para processar e otimizar imagens
def melhorar_qualidade_imagem(foto_bytes):
    """Força a foto para modo retrato e retorna os bytes da imagem processada"""
    try:
        imagem = Image.open(io.BytesIO(foto_bytes))
        
        # Converter para RGB se necessário
        if imagem.mode != 'RGB':
            imagem = imagem.convert('RGB')
        
        # FORÇA MODO RETRATO: Se a largura for maior que a altura, gira 90 graus
        width, height = imagem.size
        if width > height:
            imagem = imagem.rotate(-90, expand=True)
            
        # Salvar a imagem processada em um buffer
        buffer = io.BytesIO()
        imagem.save(buffer, format='JPEG', quality=95)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Erro ao processar imagem: {str(e)}")
        # Em caso de erro, retornar a imagem original sem processamento
        return foto_bytes

# Configuração do banco de dados SQLite
DB_PATH = "dados.db"

# Função para criar o banco de dados e tabelas se não existirem
def inicializar_banco_dados():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Criar tabela de usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        senha TEXT NOT NULL,
        tipo TEXT DEFAULT 'colaborador'
    )
    ''')
    
    # Criar tabela de transações
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_transacao TEXT UNIQUE,
        usuario TEXT NOT NULL,
        tipo TEXT NOT NULL,
        valor REAL NOT NULL,
        descricao TEXT,
        perfil TEXT NOT NULL,
        data TEXT NOT NULL,
        caminho_foto TEXT
    )
    ''')
    # Adicionar coluna origem_saldo se não existir
    try:
        cursor.execute("ALTER TABLE transacoes ADD COLUMN origem_saldo TEXT DEFAULT 'colaborador'")
    except sqlite3.OperationalError:
        pass  # Coluna já existe

    # Adicionar coluna caixa_inicio se não existir (data de início da contagem para entradas de caixa do colaborador)
    try:
        cursor.execute("ALTER TABLE transacoes ADD COLUMN caixa_inicio TEXT")
    except sqlite3.OperationalError:
        pass  # Coluna já existe

    conn.commit()
    conn.close()

# Inicializar o banco de dados
inicializar_banco_dados()

# Função para limpar backups antigos
def limpar_backups_antigos():
    try:
        backup_dir = "backups"
        if os.path.exists(backup_dir):
            # Listar todos os arquivos de backup
            backups = [f for f in os.listdir(backup_dir) if f.startswith("dados_backup_")]
            # Ordenar por data (mais recentes primeiro)
            backups.sort(reverse=True)
            
            # Manter apenas os últimos 14 backups (1 semana de backups duas vezes ao dia)
            for backup in backups[14:]:
                os.remove(os.path.join(backup_dir, backup))
    except Exception as e:
        st.error(f"Erro ao limpar backups antigos: {str(e)}")

# Função para criar backup do banco de dados
def criar_backup_banco_dados():
    try:
        hora_atual = datetime.now().hour
        minuto_atual = datetime.now().minute
        
        # Só fazer backup às 12h e 00h
        if hora_atual in [0, 12] and minuto_atual < 5:  # Nos primeiros 5 minutos da hora
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            # Usar apenas data e hora no nome do arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H00")
            backup_path = os.path.join(backup_dir, f"dados_backup_{timestamp}.db")
            
            # Verificar se já existe backup dessa hora
            if not os.path.exists(backup_path) and os.path.exists(DB_PATH):
                # Criar uma cópia do banco de dados
                shutil.copy2(DB_PATH, backup_path)
                # Limpar backups antigos após criar um novo
                limpar_backups_antigos()
                return True
                
        return True  # Retorna True mesmo quando não faz backup para não gerar erros
    except Exception as e:
        st.error(f"Erro ao criar backup: {str(e)}")
        return False

# Funções para operações com o banco de dados
def adicionar_usuario(nome, senha):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar se o usuário já existe
        cursor.execute("SELECT * FROM usuarios WHERE nome = ?", (nome,))
        if cursor.fetchone():
            conn.close()
            return False
            
        # Adicionar o novo usuário
        cursor.execute(
            "INSERT INTO usuarios (nome, senha, tipo) VALUES (?, ?, ?)",
            (nome, senha, "colaborador")
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar usuário: {str(e)}")
        return False

def verificar_usuario(nome, senha):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Buscar usuário pelo nome e senha
        cursor.execute("SELECT tipo FROM usuarios WHERE nome = ? AND senha = ?", (nome, senha))
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            return resultado[0]  # Retorna o tipo do usuário
        return None
    except Exception as e:
        st.error(f"Erro ao verificar usuário: {str(e)}")
        return None

# Utilitário: extrair data (date) de strings nos formatos usados no app
def extrair_data_para_date(data_str):
    try:
        if not data_str:
            return None
        s = str(data_str).strip()
        # ISO YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS
        if len(s) >= 10 and s[4] == '-':
            return datetime.strptime(s[:10], '%Y-%m-%d').date()
        # BR DD/MM/YYYY ou DD/MM/YYYY HH:MM:SS
        if '/' in s and len(s) >= 10:
            return datetime.strptime(s[:10], '%d/%m/%Y').date()
        # fallback: try isoformat parse
        try:
            return datetime.fromisoformat(s.split(' ')[0]).date()
        except:
            return None
    except:
        return None

def adicionar_transacao(usuario, tipo, valor, descricao, perfil, data, foto=None, origem_saldo="colaborador"):
    try:
        # Gerar um ID único para a transação
        id_transacao = str(uuid.uuid4())
        
        # Converter o valor para float
        valor_float = converter_para_float(valor)
        
        # Verifica se a data está no formato brasileiro e converte para ISO se necessário
        try:
            if '/' in data: 
                partes = data.split(' ', 1)
                data_parte = partes[0]
                hora_parte = partes[1] if len(partes) > 1 else ""
                data_obj = datetime.strptime(data_parte, '%d/%m/%Y')
                data_iso = data_obj.strftime('%Y-%m-%d')
                data = data_iso + " " + hora_parte
        except:
            pass

        # SALDO ANTERIOR DO COLABORADOR (antes de inserir)
        try:
            prev_saldo_colab = obter_saldos_separados(usuario).get('colaborador', 0.0)
        except:
            prev_saldo_colab = 0.0

        # Definir caixa_inicio quando aplicável (REGRAS):
        # - perfil == "Entrada de Caixa"
        # - origem_saldo == "colaborador"
        # - saldo anterior é (praticamente) zero
        # - após a entrada, o saldo ficará positivo
        caixa_inicio = None
        try:
            tol = 1e-9
            if perfil == "Entrada de Caixa" and origem_saldo == "colaborador":
                saldo_apos = prev_saldo_colab + valor_float
                if abs(prev_saldo_colab) < tol and saldo_apos > 0:
                    d = extrair_data_para_date(data)
                    if d:
                        caixa_inicio = d.strftime('%Y-%m-%d')
        except:
            caixa_inicio = None

        # Salvar a foto se existir
        caminho_foto = None
        if foto is not None:
            try:
                if hasattr(foto, 'read'):
                    foto_bytes = foto.read()
                else:
                    foto_bytes = foto.getvalue()
                
                try:
                    Image.open(io.BytesIO(foto_bytes))
                except:
                    pass
                
                if foto_bytes:
                    diretorio_fotos = "fotos"
                    if not os.path.exists(diretorio_fotos):
                        os.makedirs(diretorio_fotos)
                    caminho_foto = os.path.join(diretorio_fotos, f"{id_transacao}.jpg")
                    try:
                        foto_processada = melhorar_qualidade_imagem(foto_bytes)
                        with open(caminho_foto, "wb") as f:
                            f.write(foto_processada)
                        
                        if os.path.exists(caminho_foto):
                            tamanho = os.path.getsize(caminho_foto)
                            if tamanho < 100:
                                raise Exception("Arquivo de foto inválido")
                            
                            with Image.open(caminho_foto) as img:
                                width, height = img.size
                                if width == 0 or height == 0:
                                    raise Exception("Dimensões da imagem inválidas")
                        else:
                            raise Exception("Arquivo não foi criado")
                            
                    except Exception as e:
                        st.error(f"Erro ao salvar foto: {str(e)}")
                        try:
                            with open(caminho_foto, "wb") as f:
                                f.write(foto_bytes)
                            if not (os.path.exists(caminho_foto) and os.path.getsize(caminho_foto) > 100):
                                st.error("Não foi possível salvar a foto. Tente novamente.")
                                caminho_foto = None
                        except Exception as e2:
                            st.error(f"Erro final ao salvar foto: {str(e2)}")
                            caminho_foto = None
            except Exception as e:
                st.error(f"Erro ao processar o upload da foto: {str(e)}")
                caminho_foto = None
        
        # Adicionar a transação no banco de dados
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO transacoes (id_transacao, usuario, tipo, valor, descricao, perfil, data, caminho_foto, origem_saldo, caixa_inicio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (id_transacao, usuario, tipo, valor_float, descricao, perfil, data, caminho_foto, origem_saldo, caixa_inicio)
        )
        
        conn.commit()
        conn.close()
        
        # Após inserir, verificar se deve limpar caixa_inicio
        # Regra: se a transação é de Caixa (Entrada/Saída) do colaborador e o saldo ficou ZERO -> limpar contagem
        try:
            if origem_saldo == "colaborador" and perfil in ["Entrada de Caixa", "Saída de Caixa"]:
                new_saldo_colab = obter_saldos_separados(usuario).get('colaborador', 0.0)
                if abs(new_saldo_colab) < 1e-9:
                    conn2 = sqlite3.connect(DB_PATH)
                    cur2 = conn2.cursor()
                    try:
                        cur2.execute("UPDATE transacoes SET caixa_inicio = NULL WHERE usuario = ?", (usuario,))
                        conn2.commit()
                    finally:
                        conn2.close()
        except Exception:
            pass
        
        # Criar backup após adicionar transação
        criar_backup_banco_dados()
        
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar transação: {str(e)}")
        return False

def adicionar_transacao(usuario, tipo, valor, descricao, perfil, data, foto=None, origem_saldo="colaborador"):
    try:
        # Gerar um ID único para a transação
        id_transacao = str(uuid.uuid4())
        
        # Converter o valor para float
        valor_float = converter_para_float(valor)
        
        # Verifica se a data está no formato brasileiro e converte para ISO se necessário
        try:
            if '/' in data: 
                partes = data.split(' ', 1)
                data_parte = partes[0]
                hora_parte = partes[1] if len(partes) > 1 else ""
                data_obj = datetime.strptime(data_parte, '%d/%m/%Y')
                data_iso = data_obj.strftime('%Y-%m-%d')
                data = data_iso + " " + hora_parte
        except:
            pass

        # SALDO ANTERIOR DO COLABORADOR (antes de inserir)
        try:
            prev_saldo_colab = obter_saldos_separados(usuario).get('colaborador', 0.0)
        except:
            prev_saldo_colab = 0.0

        # Definir status_caixa: só para transações de CAIXA (Entrada/Saída de Caixa)
        status_caixa = None
        try:
            tol = 1e-9
            
            # Apenas transações de CAIXA colaborador podem ter status_caixa
            if origem_saldo == "colaborador" and perfil in ["Entrada de Caixa", "Saída de Caixa"]:
                
                # ABERTURA: Entrada de Caixa quando saldo estava zerado
                if perfil == "Entrada de Caixa" and abs(prev_saldo_colab) < tol:
                    d = extrair_data_para_date(data)
                    if d:
                        status_caixa = d.strftime('%Y-%m-%d')
                
                # FECHAMENTO: Saída de Caixa (sempre)
                elif perfil == "Saída de Caixa":
                    d = extrair_data_para_date(data)
                    if d:
                        status_caixa = d.strftime('%Y-%m-%d')
                
                # FECHAMENTO: Entrada de Caixa que zera saldo negativo
                elif perfil == "Entrada de Caixa":
                    saldo_apos = prev_saldo_colab + valor_float
                    if prev_saldo_colab < -tol and abs(saldo_apos) < tol:
                        d = extrair_data_para_date(data)
                        if d:
                            status_caixa = d.strftime('%Y-%m-%d')
        except:
            status_caixa = None

        # Salvar a foto se existir
        caminho_foto = None
        if foto is not None:
            try:
                if hasattr(foto, 'read'):
                    foto_bytes = foto.read()
                else:
                    foto_bytes = foto.getvalue()
                
                try:
                    Image.open(io.BytesIO(foto_bytes))
                except:
                    pass
                
                if foto_bytes:
                    diretorio_fotos = "fotos"
                    if not os.path.exists(diretorio_fotos):
                        os.makedirs(diretorio_fotos)
                    caminho_foto = os.path.join(diretorio_fotos, f"{id_transacao}.jpg")
                    try:
                        foto_processada = melhorar_qualidade_imagem(foto_bytes)
                        with open(caminho_foto, "wb") as f:
                            f.write(foto_processada)
                        
                        if os.path.exists(caminho_foto):
                            tamanho = os.path.getsize(caminho_foto)
                            if tamanho < 100:
                                raise Exception("Arquivo de foto inválido")
                            
                            with Image.open(caminho_foto) as img:
                                width, height = img.size
                                if width == 0 or height == 0:
                                    raise Exception("Dimensões da imagem inválidas")
                        else:
                            raise Exception("Arquivo não foi criado")
                            
                    except Exception as e:
                        st.error(f"Erro ao salvar foto: {str(e)}")
                        try:
                            with open(caminho_foto, "wb") as f:
                                f.write(foto_bytes)
                            if not (os.path.exists(caminho_foto) and os.path.getsize(caminho_foto) > 100):
                                st.error("Não foi possível salvar a foto. Tente novamente.")
                                caminho_foto = None
                        except Exception as e2:
                            st.error(f"Erro final ao salvar foto: {str(e2)}")
                            caminho_foto = None
            except Exception as e:
                st.error(f"Erro ao processar o upload da foto: {str(e)}")
                caminho_foto = None
        
        # Adicionar a transação no banco de dados
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transacoes (id_transacao, usuario, tipo, valor, descricao, perfil, data, caminho_foto, origem_saldo, status_caixa) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (id_transacao, usuario, tipo, valor_float, descricao, perfil, data, caminho_foto, origem_saldo, status_caixa)
        )
        conn.commit()
        conn.close()

        # NÃO limpar status_caixa - as datas devem permanecer para relatórios

        # Criar backup após adicionar transação
        criar_backup_banco_dados()
        
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar transação: {str(e)}")
        return False

def excluir_transacao(id_transacao):
    try:
        # Obter informações da transação antes de excluir
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT caminho_foto, usuario, origem_saldo, perfil, status_caixa FROM transacoes WHERE id_transacao = ?", (id_transacao,))
        resultado = cursor.fetchone()
        
        if not resultado:
            conn.close()
            return False
        
        caminho_foto = resultado[0]
        usuario = resultado[1]
        origem_saldo = resultado[2] if resultado[2] else 'colaborador'
        perfil = resultado[3]
        tinha_status_caixa = resultado[4]
        
        # Excluir a foto se existir
        if caminho_foto and os.path.exists(caminho_foto):
            try:
                os.remove(caminho_foto)
            except:
                pass  # Se não conseguir excluir a foto, continua com a exclusão da transação
        
        # Excluir a transação do banco de dados
        cursor.execute("DELETE FROM transacoes WHERE id_transacao = ?", (id_transacao,))
        conn.commit()
        conn.close()
        
        # Se era uma transação de colaborador, recalcular (qualquer transação pode afetar caixa)
        if origem_saldo == 'colaborador':
            recalcular_status_caixa_usuario(usuario)
        
        # Criar backup após excluir transação
        criar_backup_banco_dados()
        
        return True
    except Exception as e:
        st.error(f"Erro ao excluir transação: {str(e)}")
        return False


def recalcular_status_caixa_usuario(usuario):
    """
    Recalcula o status_caixa para todas as transações de caixa do colaborador.
    Chamada após exclusão ou edição de transações de caixa.
    
    Lógica:
    - ABERTURA: Entrada de Caixa quando saldo estava zerado
    - FECHAMENTO: Qualquer transação que zera o saldo (Saída de Caixa OU entrada que abate saldo negativo)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Limpar todos os status_caixa do usuário primeiro
        cursor.execute("""
            UPDATE transacoes 
            SET status_caixa = NULL 
            WHERE usuario = ? AND origem_saldo = 'colaborador'
        """, (usuario,))
        
        # Buscar todas as transações do usuário ordenadas por data
        cursor.execute("""
            SELECT id_transacao, perfil, valor, data, origem_saldo
            FROM transacoes 
            WHERE usuario = ? 
            ORDER BY data ASC
        """, (usuario,))
        
        transacoes = cursor.fetchall()
        
        # Simular o saldo para encontrar quando abre e fecha caixa
        saldo_colab = 0.0
        tol = 1e-9
        caixa_aberto = False  # Flag para saber se há caixa aberto
        
        for trans in transacoes:
            id_trans, perfil, valor, data, origem = trans
            
            # Só processar transações de origem colaborador
            if origem != 'colaborador':
                continue
            
            saldo_antes = saldo_colab
            
            # Atualizar saldo simulado baseado no perfil
            if perfil == "Entrada de Caixa":
                saldo_colab += valor
                
                # ABERTURA: Entrada de Caixa quando saldo estava zerado
                if abs(saldo_antes) < tol and not caixa_aberto:
                    caixa_aberto = True
                    try:
                        d = extrair_data_para_date(data)
                        if d:
                            cursor.execute("""
                                UPDATE transacoes 
                                SET status_caixa = ? 
                                WHERE id_transacao = ?
                            """, (d.strftime('%Y-%m-%d'), id_trans))
                    except:
                        pass
                # FECHAMENTO: Entrada que zera saldo negativo
                elif saldo_antes < -tol and abs(saldo_colab) < tol:
                    caixa_aberto = False
                    try:
                        d = extrair_data_para_date(data)
                        if d:
                            cursor.execute("""
                                UPDATE transacoes 
                                SET status_caixa = ? 
                                WHERE id_transacao = ?
                            """, (d.strftime('%Y-%m-%d'), id_trans))
                    except:
                        pass
                        
            elif perfil == "Saída de Caixa":
                saldo_colab -= valor
                
                # FECHAMENTO: Saída de Caixa (sempre marca como fechamento)
                caixa_aberto = False
                try:
                    d = extrair_data_para_date(data)
                    if d:
                        cursor.execute("""
                            UPDATE transacoes 
                            SET status_caixa = ? 
                            WHERE id_transacao = ?
                        """, (d.strftime('%Y-%m-%d'), id_trans))
                except:
                    pass
                    
            else:
                # Outras transações (saídas normais ou entradas normais)
                # Entrada normal (não é Entrada de Caixa)
                if perfil not in ["Saída de Caixa", "Entrada de Caixa"]:
                    # Pode ser entrada ou saída dependendo do contexto
                    # Se for entrada normal que zera saldo negativo
                    if saldo_antes < -tol:
                        saldo_colab += valor
                        # FECHAMENTO: Entrada normal que zera saldo negativo
                        if abs(saldo_colab) < tol:
                            caixa_aberto = False
                            try:
                                d = extrair_data_para_date(data)
                                if d:
                                    cursor.execute("""
                                        UPDATE transacoes 
                                        SET status_caixa = ? 
                                        WHERE id_transacao = ?
                                    """, (d.strftime('%Y-%m-%d'), id_trans))
                            except:
                                pass
                    else:
                        # Saída normal
                        saldo_colab -= valor
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        st.error(f"Erro ao recalcular status_caixa: {str(e)}")


def recalcular_status_caixa_usuario(usuario):
    """
    Recalcula o status_caixa para todas as transações de caixa do colaborador.
    Chamada após exclusão ou edição de transações de caixa.
    
    Lógica:
    - ABERTURA: Entrada de Caixa quando saldo estava zerado
    - FECHAMENTO: Qualquer transação que zera o saldo (Saída de Caixa OU entrada que abate saldo negativo)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Limpar todos os status_caixa do usuário primeiro
        cursor.execute("""
            UPDATE transacoes 
            SET status_caixa = NULL 
            WHERE usuario = ? AND origem_saldo = 'colaborador'
        """, (usuario,))
        
        # Buscar todas as transações do usuário ordenadas por data
        cursor.execute("""
            SELECT id_transacao, perfil, valor, data, origem_saldo
            FROM transacoes 
            WHERE usuario = ? 
            ORDER BY data ASC
        """, (usuario,))
        
        transacoes = cursor.fetchall()
        
        # Simular o saldo para encontrar quando abre e fecha caixa
        saldo_colab = 0.0
        tol = 1e-9
        caixa_aberto = False  # Flag para saber se há caixa aberto
        
        for trans in transacoes:
            id_trans, perfil, valor, data, origem = trans
            
            # Só processar transações de origem colaborador
            if origem != 'colaborador':
                continue
            
            saldo_antes = saldo_colab
            
            # Atualizar saldo simulado baseado no perfil
            if perfil == "Entrada de Caixa":
                saldo_colab += valor
                
                # ABERTURA: Entrada de Caixa quando saldo estava zerado
                if abs(saldo_antes) < tol and not caixa_aberto:
                    caixa_aberto = True
                    try:
                        d = extrair_data_para_date(data)
                        if d:
                            cursor.execute("""
                                UPDATE transacoes 
                                SET status_caixa = ? 
                                WHERE id_transacao = ?
                            """, (d.strftime('%Y-%m-%d'), id_trans))
                    except:
                        pass
                # FECHAMENTO: Entrada que zera saldo negativo
                elif saldo_antes < -tol and abs(saldo_colab) < tol:
                    caixa_aberto = False
                    try:
                        d = extrair_data_para_date(data)
                        if d:
                            cursor.execute("""
                                UPDATE transacoes 
                                SET status_caixa = ? 
                                WHERE id_transacao = ?
                            """, (d.strftime('%Y-%m-%d'), id_trans))
                    except:
                        pass
                        
            elif perfil == "Saída de Caixa":
                saldo_colab -= valor
                
                # FECHAMENTO: Saída de Caixa (sempre marca como fechamento)
                caixa_aberto = False
                try:
                    d = extrair_data_para_date(data)
                    if d:
                        cursor.execute("""
                            UPDATE transacoes 
                            SET status_caixa = ? 
                            WHERE id_transacao = ?
                        """, (d.strftime('%Y-%m-%d'), id_trans))
                except:
                    pass
                    
            else:
                # Outras transações (saídas normais ou entradas normais)
                # Entrada normal (não é Entrada de Caixa)
                if perfil not in ["Saída de Caixa", "Entrada de Caixa"]:
                    # Pode ser entrada ou saída dependendo do contexto
                    # Se for entrada normal que zera saldo negativo
                    if saldo_antes < -tol:
                        saldo_colab += valor
                        # FECHAMENTO: Entrada normal que zera saldo negativo
                        if abs(saldo_colab) < tol:
                            caixa_aberto = False
                            try:
                                d = extrair_data_para_date(data)
                                if d:
                                    cursor.execute("""
                                        UPDATE transacoes 
                                        SET status_caixa = ? 
                                        WHERE id_transacao = ?
                                    """, (d.strftime('%Y-%m-%d'), id_trans))
                            except:
                                pass
                    else:
                        # Saída normal
                        saldo_colab -= valor
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        st.error(f"Erro ao recalcular status_caixa: {str(e)}")
def obter_transacoes_usuario(usuario):
    try:
        conn = sqlite3.connect(DB_PATH)
        # Usar row_factory para obter resultados como dicionários
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Buscar todas as transações do usuário
        cursor.execute("SELECT * FROM transacoes WHERE usuario = ? ORDER BY data DESC", (usuario,))
        transacoes = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return transacoes
    except Exception as e:
        st.error(f"Erro ao obter transações: {str(e)}")
        return []

def obter_todas_transacoes():
    try:
        conn = sqlite3.connect(DB_PATH)
        # Usar row_factory para obter resultados como dicionários
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Buscar todas as transações
        cursor.execute("SELECT * FROM transacoes ORDER BY data DESC")
        transacoes = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return transacoes
    except Exception as e:
        st.error(f"Erro ao obter todas as transações: {str(e)}")
        return []

def obter_saldos_separados(usuario):
    """Calcula os saldos do colaborador e emprestado separadamente"""
    try:
        transacoes = obter_transacoes_usuario(usuario)
        saldo_colaborador = 0.0
        saldo_emprestado = 0.0
        
        for t in transacoes:
            perfil = t.get('perfil', '').strip()
            origem = t.get('origem_saldo', 'colaborador').strip()
            valor = obter_valor_numerico(t.get('valor', 0))
            
            if origem == 'colaborador':
                if perfil == "Entrada de Caixa":
                    saldo_colaborador += valor
                else:
                    saldo_colaborador -= valor
            else:  # emprestado
                if perfil == "Entrada de Caixa":
                    saldo_emprestado += valor
                else:
                    saldo_emprestado -= valor
                    
        return {
            'colaborador': saldo_colaborador,
            'emprestado': saldo_emprestado,
            'total': saldo_colaborador + saldo_emprestado
        }
    except Exception as e:
        st.error(f"Erro ao calcular saldos: {str(e)}")
        return {'colaborador': 0.0, 'emprestado': 0.0, 'total': 0.0}

def obter_saldo(usuario):
    """Mantida para compatibilidade, agora usa obter_saldos_separados"""
    saldos = obter_saldos_separados(usuario)
    return saldos['total']

# Função para obter a cor do saldo de acordo com o valor
def cor_do_saldo(saldo):
    if (saldo >= 1000):
        return "blue"
    elif (saldo >= 500):
        return "green"
    elif (saldo >= 0):
        return "orange"
    else:
        return "red"

# Função para criar um DataFrame com as transações
def criar_dataframe_transacoes(transacoes):
    df_data = []
    for t in transacoes:
        tipo_display = t.get('tipo', '-').capitalize()
        valor_bruto = t.get('valor', '0')
        try:
            valor_num = converter_para_float(valor_bruto)
            valor_display = f"{valor_num:.2f}"
        except:
            valor_display = "0.00"
        perfil_display = t.get('perfil', '-')
        descricao_display = t.get('descricao', '-')
        data_display = t.get('data', '-')
        id_transacao = t.get('id_transacao', '')
        caminho_foto = t.get('caminho_foto', '')
        # Tenta converter a data para formato brasileiro se possível
        try:
            if len(data_display) >= 10:
                if data_display[4] == '-':
                    data_obj = datetime.strptime(data_display[:10], '%Y-%m-%d')
                    hora_parte = data_display[10:19] if len(data_display) > 10 else ""
                    data_display = data_obj.strftime('%d/%m/%Y') + hora_parte
        except:
            pass
        simbolo = "+" if perfil_display == "Entrada de Caixa" else "-"
        cor = "green" if perfil_display == "Entrada de Caixa" else "red"
        # Exibir data e hora
        try:
            if ' ' in data_display:
                data_ordenacao = data_display.split(' ')[0]
                hora_ordenacao = data_display.split(' ')[1][:5]
            else:
                data_ordenacao = data_display
                hora_ordenacao = "00:00"
        except:
            data_ordenacao = data_display
            hora_ordenacao = "00:00"
        df_data.append({
            "Data": data_display,
            "Hora": hora_ordenacao,
            "Data_Ordenacao": data_ordenacao,
            "Perfil": perfil_display,
            "Valor": valor_num,
            "Valor_Display": valor_display.replace(".", ","),
            "Símbolo": simbolo,
            "Cor": cor,
            "Descrição": descricao_display,
            "ID": id_transacao,
            "Tipo": "Entrada" if perfil_display == "Entrada de Caixa" else "Saída",
            "Foto": caminho_foto
        })
    df = pd.DataFrame(df_data)
    return df.sort_values(by=["Data_Ordenacao", "Hora"], ascending=False)


def atualizar_transacao(id_transacao, tipo, valor, descricao, perfil, data, foto=None):
    try:
        # Converter o valor para float
        valor_float = converter_para_float(valor)
        
        # Verifica se a data está no formato brasileiro e converte para ISO se necessário
        try:
            if '/' in data: 
                # Extrair a parte da data e da hora
                partes = data.split(' ', 1)
                data_parte = partes[0]
                hora_parte = partes[1] if len(partes) > 1 else ""
                
                # Converter a data para formato ISO
                data_obj = datetime.strptime(data_parte, '%d/%m/%Y')
                data_iso = data_obj.strftime('%Y-%m-%d')
                
                # Reconstruir a string de data/hora
                data = data_iso + " " + hora_parte
        except:
            pass
        
        # Obter dados da transação atual
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT caminho_foto, usuario, origem_saldo FROM transacoes WHERE id_transacao = ?", (id_transacao,))
        resultado = cursor.fetchone()
        
        if not resultado:
            conn.close()
            return False
            
        foto_anterior = resultado[0]
        usuario = resultado[1]
        origem_saldo = resultado[2] if resultado[2] else 'colaborador'
        
        # Calcular saldo ANTES da atualização (removendo o efeito da transação atual)
        cursor.execute("SELECT perfil, valor FROM transacoes WHERE id_transacao = ?", (id_transacao,))
        transacao_atual = cursor.fetchone()
        conn.close()
        
        if transacao_atual:
            perfil_anterior = transacao_atual[0]
            valor_anterior = transacao_atual[1]
            
            # Saldo atual do colaborador
            saldo_atual = obter_saldos_separados(usuario).get('colaborador', 0.0)
            
            # Reverter o efeito da transação anterior para calcular saldo antes dela
            if origem_saldo == 'colaborador':
                if perfil_anterior == "Entrada de Caixa":
                    saldo_antes = saldo_atual - valor_anterior
                else:
                    saldo_antes = saldo_atual + valor_anterior
            else:
                saldo_antes = saldo_atual
        else:
            saldo_antes = obter_saldos_separados(usuario).get('colaborador', 0.0)
            
        # Salvar a foto se existir
        caminho_foto = foto_anterior  # Manter a foto anterior se não houver uma nova
        if foto is not None:
            try:
                foto_bytes = foto.getvalue() if hasattr(foto, 'getvalue') else None
                # Processar qualquer foto sem validação rigorosa
                if foto_bytes:
                    diretorio_fotos = "fotos"
                    if not os.path.exists(diretorio_fotos):
                        os.makedirs(diretorio_fotos)
                    # Remover foto anterior se existir
                    if foto_anterior and os.path.exists(foto_anterior):
                        try:
                            os.remove(foto_anterior)
                        except:
                            pass
                    # Salvar nova foto
                    caminho_foto = os.path.join(diretorio_fotos, f"{id_transacao}.jpg")
                    try:
                        with open(caminho_foto, "wb") as f:
                            f.write(foto_bytes)
                    except Exception as e:
                        st.warning(f"Aviso ao salvar a foto: {str(e)}")
                        # Manter caminho mesmo se houver erro ao salvar
            except Exception as e:
                st.error(f"Erro ao processar o upload da foto: {str(e)}")
                caminho_foto = foto_anterior
        
        # Atualizar status_caixa: só para transações de CAIXA (Entrada/Saída de Caixa)
        status_caixa = None
        try:
            tol = 1e-9
            
            # Apenas transações de CAIXA colaborador podem ter status_caixa
            if origem_saldo == "colaborador" and perfil in ["Entrada de Caixa", "Saída de Caixa"]:
                
                # ABERTURA: Entrada de Caixa quando saldo estava zerado
                if perfil == "Entrada de Caixa" and abs(saldo_antes) < tol:
                    d = extrair_data_para_date(data)
                    if d:
                        status_caixa = d.strftime('%Y-%m-%d')
                
                # FECHAMENTO: Saída de Caixa (sempre)
                elif perfil == "Saída de Caixa":
                    d = extrair_data_para_date(data)
                    if d:
                        status_caixa = d.strftime('%Y-%m-%d')
                
                # FECHAMENTO: Entrada de Caixa que zera saldo negativo
                elif perfil == "Entrada de Caixa":
                    saldo_apos = saldo_antes + valor_float
                    if saldo_antes < -tol and abs(saldo_apos) < tol:
                        d = extrair_data_para_date(data)
                        if d:
                            status_caixa = d.strftime('%Y-%m-%d')
        except:
            status_caixa = None

        # Atualizar a transação no banco de dados
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE transacoes SET tipo = ?, valor = ?, descricao = ?, perfil = ?, data = ?, caminho_foto = ?, status_caixa = ? WHERE id_transacao = ?",
            (tipo, valor_float, descricao, perfil, data, caminho_foto, status_caixa, id_transacao)
        )
        
        conn.commit()
        conn.close()
        
        # Recalcular status_caixa apenas se for transação de CAIXA colaborador
        if origem_saldo == 'colaborador' and perfil in ['Entrada de Caixa', 'Saída de Caixa']:
            recalcular_status_caixa_usuario(usuario)
        
        # Criar backup após atualizar transação
        criar_backup_banco_dados()
        
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar transação: {str(e)}")
        return False

# Função para calcular saldo colaborador até uma data limite
def calcular_saldo_colaborador_ate(usuario, data_limite_str):
    """
    Calcula o saldo do colaborador para 'usuario' considerando apenas transações
    com data STRICTAMENTE menor que data_limite_str (usa apenas a parte de data).
    Retorna float.
    """
    try:
        trans = obter_transacoes_usuario(usuario)
        # converter limite para date
        limite = extrair_data_para_date(data_limite_str)
        if limite is None:
            return 0.0
        saldo = 0.0
        # ordenar por data (asc)
        def key_dt(x):
            d = extrair_data_para_date(x.get('data') or "")
            return d or datetime.min.date()
        trans_sorted = sorted(trans, key=key_dt)
        for t in trans_sorted:
            d = extrair_data_para_date(t.get('data') or "")
            if d is None:
                continue
            if d < limite:
                origem = t.get('origem_saldo', 'colaborador')
                perfil_t = t.get('perfil', '')
                valor_t = obter_valor_numerico(t.get('valor', 0))
                if origem == 'colaborador':
                    if perfil_t == "Entrada de Caixa":
                        saldo += valor_t
                    else:
                        saldo -= valor_t
            else:
                break
        return saldo
    except:
        return 0.0

# Interface inicial
st.title("Gestão Financeira - Programa Zelar")

# Interface principal
menu = ["Login", "Registrar", "Supervisor"]
escolha = st.sidebar.selectbox("Menu", menu)

if escolha == "Registrar":
    st.subheader("Criar Conta")
    nome = st.text_input("Nome")
    senha = st.text_input("Senha", type="password")
    senha_supervisor = st.text_input("Senha do Supervisor", type="password", help="Digite a senha de um supervisor para autorizar o cadastro")
    if st.button("Entrar"):  # Botão padronizado
        if nome and senha and senha_supervisor:
            # Verificar se existe algum supervisor com a senha fornecida
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE tipo = 'supervisor' AND senha = ?", (senha_supervisor,))
            supervisor = cursor.fetchone()
            conn.close()
            
            if supervisor:
                if adicionar_usuario(nome, senha):
                    st.success("Conta criada com sucesso!")
                else:
                    st.error("Usuário já existe ou ocorreu um erro ao registrar!")
            else:
                st.error("Senha do supervisor incorreta!")
        else:
            st.warning("Por favor, preencha todos os campos!")

elif escolha == "Login":
    st.subheader("Login")
    if "usuario" not in st.session_state:
        nome = st.text_input("Nome")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):  # Botão padronizado
            if nome and senha:
                tipo_usuario = verificar_usuario(nome, senha)
                if tipo_usuario:
                    st.session_state["usuario"] = nome
                    st.session_state["tipo"] = tipo_usuario
                    st.success(f"Bem-vindo, {st.session_state['usuario']}!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos")
            else:
                st.warning("Por favor, preencha todos os campos!")
    else:
        # Mostra informações do usuário logado e botão de logoff
        st.success(f"Você está logado como: {st.session_state['usuario']}")
        
        if st.button("Sair"):
            # Limpa os dados da sessão
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        # Formulário para adicionar nova transação
        st.subheader("Adicionar Nova Transação")
        with st.form(key="adicionar_transacao"):
            perfil = st.selectbox("Perfil da Transação", ["Café da Manhã", "Almoço", "Janta", "Outros Serviços", "Saída de Caixa" , "Entrada de Caixa"])
            origem_saldo = st.radio(
                "Origem do Saldo:",
                ["colaborador", "emprestado"],
                horizontal=True,
                help="Escolha se esta transação usa seu saldo próprio ou saldo emprestado"
            )
            valor_str = st.text_input("Valor", value="0,00", help="Digite o valor usando vírgula ou ponto como separador decimal (exemplo: 25,70 ou 25.70)")
            try:
                valor = converter_para_float(valor_str)
            except Exception as e:
                st.error(f"Erro ao converter valor: {str(e)}")
                valor = 0.0
            descricao = st.text_input("Descrição (opcional)")
            st.subheader("Data e Hora da Transação")
            col1, col2 = st.columns(2)
            with col1:
                data = st.date_input("Data", value=datetime.today(), format="DD/MM/YYYY")
            with col2:
                st.write("Hora")
                hora_col, min_col = st.columns(2)
                with hora_col:
                    hora_valor = st.slider("Hora", 0, 23, int(datetime.now().hour))
                with min_col:
                    minuto_valor = st.slider("Minuto", 0, 59, int(datetime.now().minute), step=5)
                hora = datetime.now().time().replace(hour=hora_valor, minute=minuto_valor)
                st.write(f"Horário selecionado: {hora_valor:02d}:{minuto_valor:02d}")
            # Interface de foto consistente com o formulário de edição
            if "mostrar_camera" not in st.session_state:
                st.session_state.mostrar_camera = False
                
            if not st.session_state.mostrar_camera:
                camera_button = st.form_submit_button("📷 Adicionar Foto (opcional)")
                if camera_button:
                    st.session_state.mostrar_camera = True
                    st.rerun()
            else:
                # Upload de arquivo aceitando todos os formatos de foto comuns
                foto = st.file_uploader("Escolher foto", 
                    type=['png', 'jpg', 'jpeg', 'bmp', 'gif', 'tiff', 'webp', 'heic', 'heif'],
                    accept_multiple_files=False, 
                    key="file_uploader",
                    help="Tire a foto o mais próximo possível da nota fiscal. Segure o celular na vertical.")
                cancelar_foto = st.form_submit_button("❌ Cancelar")
                
                # Sem preview
                if cancelar_foto:
                    st.session_state.mostrar_camera = False
                    st.session_state.foto_capturada = None
                    st.rerun()
                    
                # Armazena a foto na sessão
                if foto is not None:
                    st.session_state.foto_capturada = foto
                    st.success("Foto anexada com sucesso!")

            submeter = st.form_submit_button("Adicionar Transação")            # Lógica para processar o formulário após submissão
        if submeter:
            # Combina data e hora
            data_hora = datetime.combine(data, hora).strftime('%d/%m/%Y %H:%M:%S')
            
            # Define o tipo de transação com base no perfil
            tipo_transacao = "entrada" if perfil == "Entrada de Caixa" else "saida"
            
            # Obter foto da sessão se existir
            foto_para_salvar = st.session_state.get("foto_capturada", None)
            
            if valor > 0:  # Descrição agora é opcional
                if adicionar_transacao(st.session_state["usuario"], tipo_transacao, valor, descricao, perfil, data_hora, foto_para_salvar, origem_saldo):
                    st.success("Transação adicionada com sucesso!")
                    # Limpar os campos do formulário e estado da sessão
                    for key in ["valor_input", "descricao_input", "file_uploader", "foto_capturada", "mostrar_camera"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    time.sleep(2)  # Aumentado para dar mais tempo para processar a foto
                    st.rerun()
                else:
                    st.error("Erro ao adicionar transação. Tente novamente.")
            else:
                st.warning("Por favor, informe um valor maior que zero!")
        
        # Exibir transações do usuário com ícones de edição
        st.subheader("Minhas Transações")
        transacoes = obter_transacoes_usuario(st.session_state["usuario"])
        
        # Verificar se temos transações para exibir
        if not transacoes:
            st.info("Você ainda não possui transações registradas.")
        else:
            # Se temos uma transação selecionada para editar, mostrar o formulário de edição
            if "transacao_editando" in st.session_state:
                transacao_id = st.session_state["transacao_editando"]
                
                # Encontrar a transação pelo ID
                transacao = None
                for t in transacoes:
                    if t.get('id_transacao') == transacao_id:
                        transacao = t
                        break
                
                if transacao:
                    st.subheader("Editar Transação")
                    
                    with st.form(key="editar_transacao"):
                        # Campos para edição
                        perfil_edit = st.selectbox("Perfil da Transação", 
                                            ["Café da Manhã", "Almoço", "Janta", "Outros Serviços", "Saída de Caixa" , "Entrada de Caixa"],
                                            index=["Café da Manhã", "Almoço", "Janta", "Outros Serviços", "Saída de Caixa" , "Entrada de Caixa"].index(transacao.get('perfil', 'Outros Serviços')))
                        
                        # Campo de valor que aceita vírgula ou ponto como separador decimal
                        valor_atual = float(transacao.get('valor', 0))
                        valor_str_edit = st.text_input("Valor", value=f"{valor_atual:.2f}".replace('.', ','), 
                                            help="Digite o valor usando vírgula ou ponto como separador decimal",
                                            key="valor_edit_text")
                        valor_edit = converter_para_float(valor_str_edit)
                        
                        # Descrição original da transação
                        descricao_edit = st.text_input("Descrição (opcional)",
                                                value=transacao.get('descricao', ''))
                        
                        # Botão para upload de foto na edição
                        if "mostrar_camera_edicao" not in st.session_state:
                            st.session_state.mostrar_camera_edicao = False
                            
                        if not st.session_state.mostrar_camera_edicao:
                            camera_button = st.form_submit_button("📷 Atualizar Foto (opcional)")
                            if camera_button:
                                st.session_state.mostrar_camera_edicao = True
                                st.rerun()
                        else:
                            # Upload de arquivo ao invés de câmera
                            foto_edit = st.file_uploader("Escolher foto", type=['jpg', 'jpeg', 'png'], key="foto_edit")
                            cancelar_foto = st.form_submit_button("❌ Cancelar")
                            if cancelar_foto:
                                st.session_state.mostrar_camera_edicao = False
                                st.session_state.foto_capturada_edicao = None
                                st.rerun()
                                
                            # Armazena a foto na sessão
                            if foto_edit is not None:
                                st.session_state.foto_capturada_edicao = foto_edit
                                st.success("Nova foto anexada com sucesso!")
                        
                        # Data original da transação
                        data_original = transacao.get('data', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        
                        # Tentar converter a data para exibição
                        try:
                            if len(data_original) >= 10:
                                if data_original[4] == '-':  # Formato ISO
                                    data_obj = datetime.strptime(data_original[:10], '%Y-%m-%d')
                                    hora_str = data_original[10:16] if len(data_original) > 16 else "00:00"
                                    hora_parts = hora_str.split(':')
                                    hora_val = int(hora_parts[0]) if len(hora_parts) > 0 else 0
                                    min_val = int(hora_parts[1]) if len(hora_parts) > 1 else 0
                                else:  # Possível formato brasileiro
                                    data_obj = datetime.strptime(data_original[:10], '%d/%m/%Y')
                                    hora_str = data_original[10:16] if len(data_original) > 16 else "00:00"
                                    hora_parts = hora_str.split(':')
                                    hora_val = int(hora_parts[0]) if len(hora_parts) > 0 else 0
                                    min_val = int(hora_parts[1]) if len(hora_parts) > 1 else 0
                        except:
                            data_obj = datetime.now()
                            hora_val = 0
                            min_val = 0
                        
                        # Campos de data e hora para edição
                        col1, col2 = st.columns(2)
                        with col1:
                            data_edit = st.date_input("Data", value=data_obj, format="DD/MM/YYYY", key="data_edit")
                        
                        with col2:
                            hora_col, min_col = st.columns(2)
                            with hora_col:
                                hora_valor_edit = st.slider("Hora", 0, 23, hora_val, key="hora_edit")
                            with min_col:
                                minuto_valor_edit = st.slider("Minuto", 0, 59, min_val, step=5, key="min_edit")
                        
                        # Botões de ação para edição
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            cancelar = st.form_submit_button("Cancelar")
                        
                        with col2:
                            salvar = st.form_submit_button("Salvar Alterações")
                        
                        # Tratamento dos botões
                        if cancelar:
                            if "transacao_editando" in st.session_state:
                                del st.session_state["transacao_editando"]
                            st.rerun()
                        
                        if salvar:
                            if valor_edit <= 0:
                                st.error("O valor deve ser maior que zero!")
                            else:
                                # Combina data e hora
                                data_hora_edit = datetime.combine(
                                    data_edit, 
                                    datetime.now().time().replace(hour=hora_valor_edit, minute=minuto_valor_edit)
                                ).strftime('%d/%m/%Y %H:%M:%S')
                                
                                # Define o tipo com base no perfil
                                tipo_edit = "entrada" if perfil_edit == "Entrada de Caixa" else "saida"
                                
                                # Obtém a foto da sessão para edição, se existir
                                foto_edit_para_salvar = st.session_state.get("foto_capturada_edicao", None)
                                
                                # Atualiza a transação
                                if atualizar_transacao(transacao_id, tipo_edit, valor_edit, descricao_edit, perfil_edit, data_hora_edit, foto_edit_para_salvar):
                                    # Limpa o estado de edição e recarrega
                                    if "transacao_editando" in st.session_state:
                                        del st.session_state["transacao_editando"]
                                    if "foto_capturada_edicao" in st.session_state:
                                        del st.session_state["foto_capturada_edicao"]
                                    if "mostrar_camera_edicao" in st.session_state:
                                        del st.session_state["mostrar_camera_edicao"]
                                    st.success("Transação atualizada com sucesso!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Erro ao atualizar a transação!")
                    
                    # Botão adicional para excluir fora do formulário
                    if st.button("Excluir Transação", type="primary", help="Esta ação não pode ser desfeita!"):
                        if st.session_state.get("confirmar_exclusao") != transacao_id:
                            st.session_state["confirmar_exclusao"] = transacao_id
                            st.warning("Clique novamente para confirmar a exclusão.")
                        else:
                            if excluir_transacao(transacao_id):
                                if "transacao_editando" in st.session_state:
                                    del st.session_state["transacao_editando"]
                                if "confirmar_exclusao" in st.session_state:
                                    del st.session_state["confirmar_exclusao"]
                                st.success("Transação excluída com sucesso!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Erro ao excluir transação. Tente novamente.")
            
            # Exibir tabela de transações
            df = criar_dataframe_transacoes(transacoes)
            
            # Adicionar filtros
            st.subheader("Filtros")
            col1, col2, col3 = st.columns(3)
            with col1:
                perfis_disponiveis = ["Todos"] + sorted(df["Perfil"].unique().tolist())
                filtro_perfil = st.selectbox("Filtrar por Perfil", perfis_disponiveis)
            with col2:
                meses = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                mes_atual = datetime.now().month
                filtro_mes = st.selectbox("Filtrar por Mês", meses, index=mes_atual)
            with col3:
                anos_disponiveis = sorted(list(set([d.split("/")[-1][:4] for d in df["Data"].astype(str)])), reverse=True)
                if not anos_disponiveis:
                    anos_disponiveis = [str(datetime.now().year)]
                filtro_ano = st.selectbox("Filtrar por Ano", anos_disponiveis)
            df_filtrado = df.copy()
            if filtro_perfil != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Perfil"] == filtro_perfil]
            df_filtrado['Data_dt'] = pd.to_datetime(df_filtrado['Data'].apply(lambda x: x.split(' ')[0]), format='%d/%m/%Y')
            df_filtrado['Mes'] = df_filtrado['Data_dt'].dt.month
            df_filtrado['Ano'] = df_filtrado['Data_dt'].dt.year.astype(str)
            if filtro_mes != "Todos":
                mes_numero = meses.index(filtro_mes)
                df_filtrado = df_filtrado[df_filtrado['Mes'] == mes_numero]
            if filtro_ano:
                df_filtrado = df_filtrado[df_filtrado['Ano'] == filtro_ano]
            
            # Exibir tabela com estilo
            if not df_filtrado.empty:
                # Aplicar formatação aos valores para exibição
                df_display = df_filtrado.copy()
                df_display["Valor"] = df_display.apply(
                    lambda x: f"{x['Símbolo']} R$ {x['Valor_Display']}", axis=1
                )
                
                # Criar coluna de ações com botão de edição para cada linha
                df_display["Ações"] = None  # Coluna vazia que será preenchida com botões
                
                # Exibir a tabela com formatação personalizada
                for index, row in df_display.iterrows():
                    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 3, 1, 1])
                    with col1:
                        st.write(row["Data"].split(" ")[0])  # Apenas a data sem a hora
                    with col2:
                        st.write(row["Hora"])  # Hora
                    with col3:
                        st.write(row["Perfil"])
                    with col4:
                        # Mostrar valor com a cor correta
                        if row["Símbolo"] == "+":
                            st.markdown(f"<span style='color:green'>+ R$ {row['Valor_Display']}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<span style='color:red'>- R$ {row['Valor_Display']}</span>", unsafe_allow_html=True)
                    with col5:
                        st.write(row["Descrição"])
                    with col6:
                        if st.button("✏️", key=f"edit_{row['ID']}_{index}"):
                            st.session_state["transacao_editando"] = row["ID"]
                            st.rerun()
                        if row["Foto"] and os.path.exists(row["Foto"]):
                            foto_key = f"foto_{row['ID']}_{index}"
                            if st.button("📷", key=foto_key):
                                st.session_state[f"mostrar_foto_{row['ID']}"] = not st.session_state.get(f"mostrar_foto_{row['ID']}", False)
                                st.rerun()
                    if st.session_state.get(f"mostrar_foto_{row['ID']}", False) and row["Foto"] and os.path.exists(row["Foto"]):
                        st.image(row["Foto"], caption="Foto da transação", use_container_width=True)
                    st.markdown("---")
                
            else:
                st.info("Nenhuma transação encontrada com os filtros selecionados.")
        
        st.subheader("Saldo Atual")
        saldo = obter_saldo(st.session_state["usuario"])
        saldo_formatado = formatar_valor(saldo)
        if saldo >= 0:
            st.success(f"{saldo_formatado}")
        else:
            st.error(f"{saldo_formatado}")

        # Exibir saldos separados
        st.subheader("Saldos")
        saldos = obter_saldos_separados(st.session_state["usuario"])
        
        col1, col2 = st.columns(2)
        with col1:
            saldo_colab = saldos['colaborador']
            saldo_colab_fmt = formatar_valor(saldo_colab)
            st.markdown("**Saldo do Colaborador:**")
            if saldo_colab >= 0:
                st.success(f"{saldo_colab_fmt}")
            else:
                st.error(f"{saldo_colab_fmt}")
                st.info("💡 Este valor será devolvido pela empresa")
        
        with col2:
            saldo_emp = saldos['emprestado']
            saldo_emp_fmt = formatar_valor(saldo_emp)
            st.markdown("**Saldo Emprestado:**")
            if saldo_emp >= 0:
                st.warning(f"{saldo_emp_fmt}")
                if saldo_emp > 0:
                    st.info("💡 Este valor deve ser devolvido")
            else:
                st.error(f"{saldo_emp_fmt}")
        

elif escolha == "Supervisor":
    st.subheader("Painel do Supervisor")
    
    # Verificar se o usuário está logado e é supervisor
    if "usuario" not in st.session_state or "tipo" not in st.session_state or st.session_state["tipo"] != "supervisor":
        st.warning("Você precisa estar logado como supervisor para acessar esta área.")
        nome = st.text_input("Nome")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):  # Botão padronizado
            if nome and senha:
                tipo_usuario = verificar_usuario(nome, senha)
                if tipo_usuario == "supervisor":
                    st.session_state["usuario"] = nome
                    st.session_state["tipo"] = tipo_usuario
                    st.success(f"Bem-vindo, Supervisor {st.session_state['usuario']}!")
                    st.rerun()
                else:
                    st.error("Acesso negado. Esta área é restrita para supervisores.")
            else:
                st.warning("Por favor, preencha todos os campos!")
    else:
        # Conteúdo do painel do supervisor
            todos_registros = obter_todas_transacoes()
            usuarios = set(t.get('usuario') for t in todos_registros if t.get('usuario'))
            if usuarios:
                # Criar dados para tabela
                dados_usuarios = []
                for usuario in usuarios:
                    saldo = obter_saldo(usuario)
                    cor = cor_do_saldo(saldo)
                    status = "Excelente" if cor == "blue" else "Bom" if cor == "green" else "Regular" if cor == "orange" else "Negativo"
                    # NOVO: calcular data de fechamento do caixa (30 dias após abertura)
                    # Encontrar caixa_inicio
                    entradas_candidatas = [
                        t for t in todos_registros
                        if t.get('usuario') == usuario
                        and t.get('perfil') == 'Entrada de Caixa'
                        and t.get('origem_saldo', 'colaborador') == 'colaborador'
                    ]
                    data_fechamento = ""
                    if entradas_candidatas:
                        try:
                            entradas_sorted = sorted(
                                entradas_candidatas,
                                key=lambda x: extrair_data_para_date(x.get('data') or ""),
                                reverse=True
                            )
                            inicio_encontrado = None
                            for ent in entradas_sorted:
                                if ent.get('caixa_inicio'):
                                    inicio_encontrado = extrair_data_para_date(ent.get('caixa_inicio'))
                                    break
                                data_trans = ent.get('data') or ""
                                prev_saldo = calcular_saldo_colaborador_ate(usuario, data_trans)
                                valor_ent = obter_valor_numerico(ent.get('valor', 0))
                                saldo_depois = prev_saldo + valor_ent
                                tol = 1e-9
                                if abs(prev_saldo) < tol and saldo_depois > 0:
                                    inicio_encontrado = extrair_data_para_date(data_trans)
                                    break
                            if inicio_encontrado:
                                fechamento = inicio_encontrado + pd.Timedelta(days=30)
                                data_fechamento = fechamento.strftime('%d/%m/%Y')
                        except:
                            data_fechamento = ""
                    dados_usuarios.append({
                        "Usuário": usuario,
                        "Saldo": saldo,
                        "Saldo_Formatado": formatar_valor(saldo),
                        "Status": status,
                        "Cor": cor,
                        "Data_Fechamento_Caixa": data_fechamento
                    })
                
                # Criar dataframe e exibir
                df = pd.DataFrame(dados_usuarios)
                
                # Adicionar filtros
                st.subheader("Filtros")
                status_disponiveis = ["Todos"] + sorted(df["Status"].unique().tolist())
                filtro_status = st.selectbox("Filtrar por Status", status_disponiveis)
                
                # Aplicar filtros
                df_filtrado = df.copy()
                if filtro_status != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["Status"] == filtro_status]
                
                # Ordenar por saldo (maior para menor)
                df_filtrado = df_filtrado.sort_values(by="Saldo", ascending=False)
                
                # Exibir tabela customizada incluindo a nova coluna "Dias de Caixa"
                st.markdown("### Status de Usuários")
                # Cabeçalho
                col_u, col_s, col_sc, col_se, col_stat, col_d, col_df = st.columns([2, 2, 2, 2, 1.5, 3, 2])
                col_u.markdown("**Usuário**")
                col_s.markdown("**Saldo Total**")
                col_sc.markdown("**Saldo Colab.**")
                col_se.markdown("**Saldo Emp.**")
                col_stat.markdown("**Status**")
                col_d.markdown("**Dias de Caixa**")
                col_df.markdown("**Fechamento do Caixa**")

                hoje = datetime.now().date()
                # Para cada usuário calcular dias de caixa aberto
                # Para cada usuário calcular dias de caixa aberto
                for _, row in df_filtrado.iterrows():
                    usuario = row["Usuário"]
                    saldo_total_fmt = row["Saldo_Formatado"]
                    status = row["Status"]
                    cor = row.get("Cor", "black")
                    
                    # Calcular saldos separados
                    saldos_sep = obter_saldos_separados(usuario)
                    saldo_colab = saldos_sep.get('colaborador', 0.0)
                    saldo_emp = saldos_sep.get('emprestado', 0.0)
                    saldo_colab_fmt = formatar_valor(saldo_colab)
                    saldo_emp_fmt = formatar_valor(saldo_emp)
                    
                    # Buscar transações de caixa do colaborador com status_caixa
                    transacoes_caixa = [
                        t for t in todos_registros
                        if t.get('usuario') == usuario
                        and t.get('origem_saldo', 'colaborador') == 'colaborador'
                        and t.get('status_caixa')
                        and t.get('perfil') in ['Entrada de Caixa', 'Saída de Caixa']
                    ]
                    
                    dias_display = ""
                    dias_color = None
                    data_fechamento = ""
                    
                    if transacoes_caixa:
                        try:
                            # Ordenar por data do status_caixa
                            transacoes_ordenadas = sorted(
                                transacoes_caixa,
                                key=lambda x: extrair_data_para_date(x.get('status_caixa') or ""),
                                reverse=False
                            )
                            
                            # Procurar a última abertura e fechamento
                            ultima_abertura = None
                            ultimo_fechamento = None
                            
                            for trans in transacoes_ordenadas:
                                data_status = extrair_data_para_date(trans.get('status_caixa'))
                                perfil = trans.get('perfil')
                                
                                if data_status:
                                    if perfil == 'Entrada de Caixa':
                                        ultima_abertura = data_status
                                    elif perfil == 'Saída de Caixa':
                                        ultimo_fechamento = data_status
                            
                            # Verificar se há caixa aberto (abertura sem fechamento posterior)
                            if ultima_abertura:
                                # Se não há fechamento OU o fechamento é anterior à abertura
                                if not ultimo_fechamento or ultimo_fechamento < ultima_abertura:
                                    # Caixa está ABERTO
                                    dias = (hoje - ultima_abertura).days
                                    dias_display = f"{dias} dias de caixa em aberto"
                                    
                                    if dias >= 30:
                                        dias_color = "red"
                                    elif dias >= 25:
                                        dias_color = "orange"
                                    
                                    # Calcular data de fechamento (30 dias após abertura)
                                    fechamento_calculado = ultima_abertura + pd.Timedelta(days=30)
                                    data_fechamento = fechamento_calculado.strftime('%d/%m/%Y')
                                # Caso contrário, caixa está FECHADO - não mostrar nada
                        except:
                            dias_display = ""
                            data_fechamento = ""

                    # Renderizar linha
                    col_u, col_s, col_sc, col_se, col_stat, col_d, col_df = st.columns([2, 2, 2, 2, 1.5, 3, 2])
                    col_u.write(usuario)
                    color_map = {"blue":"#0b5394","green":"#198754","orange":"#ff9900","red":"#d9534f"}
                    saldo_color = color_map.get(cor, "black")
                    col_s.markdown(f"<span style='color:{saldo_color}; font-weight:bold'>{saldo_total_fmt}</span>", unsafe_allow_html=True)
                    col_sc.write(saldo_colab_fmt)
                    col_se.write(saldo_emp_fmt)
                    col_stat.write(status)
                    if dias_display:
                        if dias_color == "red":
                            col_d.markdown(f"<span style='color:red; font-weight:bold'>{dias_display}</span>", unsafe_allow_html=True)
                        elif dias_color == "orange":
                            col_d.markdown(f"<span style='color:orange; font-weight:bold'>{dias_display}</span>", unsafe_allow_html=True)
                        else:
                            col_d.write(dias_display)
                    else:
                        col_d.write("")
                    # Exibir data de fechamento do caixa com cor vermelha se já chegou ou passou
                    if fechamento and hoje >= fechamento:
                        col_df.markdown(f"<span style='color:red; font-weight:bold'>{data_fechamento}</span>", unsafe_allow_html=True)
                    elif data_fechamento:
                        col_df.markdown(f"<span style='color:blue; font-weight:bold'>{data_fechamento}</span>", unsafe_allow_html=True)
                    else:
                        col_df.write("")
                
                # Filtro por mês e ano
                st.subheader("Filtrar por mês e ano")
                meses = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                mes_atual = datetime.now().month
                # Corrigir: criar df_transacoes a partir de todos_registros
                df_transacoes = pd.DataFrame(todos_registros)
                df_transacoes['valor'] = df_transacoes['valor'].apply(obter_valor_numerico)
                df_transacoes['data'] = pd.to_datetime(df_transacoes['data'])
                df_transacoes['mes'] = df_transacoes['data'].dt.month
                anos_disponiveis = sorted(list(set(df_transacoes['data'].dt.year.astype(str))), reverse=True)
                if not anos_disponiveis:
                    anos_disponiveis = [str(datetime.now().year)]
                mes_selecionado = st.selectbox("Selecione o mês:", options=meses, index=mes_atual)
                ano_selecionado = st.selectbox("Selecione o ano:", options=anos_disponiveis, index=0)
                df_transacoes['Ano'] = df_transacoes['data'].dt.year.astype(str)
                if mes_selecionado == "Todos":
                    df_filtrado_mes = df_transacoes[df_transacoes['Ano'] == ano_selecionado]
                else:
                    mes_numero = meses.index(mes_selecionado)
                    df_filtrado_mes = df_transacoes[(df_transacoes['mes'] == mes_numero) & (df_transacoes['Ano'] == ano_selecionado)]

                # Dashboard Principal
                st.subheader("Dashboard Principal")
                col1, col2, col3, col4 = st.columns(4)
                
                # Filtrar apenas transações que não são do tipo Caixa
                df_saidas = df_filtrado_mes[~df_filtrado_mes['perfil'].isin(['Saída de Caixa', 'Entrada de Caixa'])]
                
                with col1:
                    total_transacoes = len(df_saidas)
                    st.metric("Total de Transações", total_transacoes)
                
                with col2:
                    valor_total = df_saidas['valor'].sum()
                    st.metric("Valor Total Gasto", f"R$ {valor_total:,.2f}")
                
                with col3:
                    usuarios_ativos = len(df_saidas['usuario'].unique())
                    st.metric("Usuários Ativos", usuarios_ativos)
                
                with col4:
                    ticket_medio = valor_total / total_transacoes if total_transacoes > 0 else 0
                    st.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}")

                # Gráficos e Visualizações
                st.subheader("Análise de Transações")
                
                # Gráfico de barras com transações por dia - apenas saídas
                df_saidas = df_filtrado_mes[~df_filtrado_mes['perfil'].isin(['Saída de Caixa', 'Entrada de Caixa'])]
                df_saidas['dia'] = df_saidas['data'].dt.day
                fig_dia = px.bar(
                    df_saidas.groupby('dia').size().reset_index(name='count'),
                    x='dia',
                    y='count',
                    title=f'Transações por Dia - {mes_selecionado}',
                    labels={'dia': 'Dia', 'count': 'Número de Saídas'}
                )
                st.plotly_chart(fig_dia, use_container_width=True)

                # Gráfico de pizza com distribuição por tipo de transação
                df_pizza = df_filtrado_mes[~df_filtrado_mes['perfil'].isin(['Saída de Caixa', 'Entrada de Caixa'])]
                fig_tipo = px.pie(
                    df_pizza,
                    names='perfil',
                    values='valor',
                    title=f'Distribuição de Custos por Tipo de Transação - {mes_selecionado}'
                )
                st.plotly_chart(fig_tipo, use_container_width=True)

                # Métricas por Usuário
                st.subheader("Métricas por Usuário")
                
                # Ranking de usuários por valor gasto
                df_usuarios = df_filtrado_mes[~df_filtrado_mes['perfil'].isin(['Saída de Caixa', 'Entrada de Caixa'])].groupby('usuario')['valor'].sum().reset_index()
                df_usuarios = df_usuarios.sort_values('valor', ascending=False)
                
                fig_ranking = px.bar(
                    df_usuarios,
                    x='usuario',
                    y='valor',
                    title=f'Ranking de Usuários por Valor Gasto - {mes_selecionado}'
                )
                st.plotly_chart(fig_ranking, use_container_width=True)

                # Alertas e Indicadores
                st.subheader("Transações por Usuário")
                
                # Usuários com saldo negativo
                usuarios_negativo = [u for u in df_filtrado_mes['usuario'].unique() if obter_saldo(u) < 0]
                if usuarios_negativo:
                    st.warning(f"Usuários com saldo negativo: {', '.join(usuarios_negativo)}")
                
                # Transações acima da média - excluindo Caixa
                df_sem_caixa = df_filtrado_mes[~df_filtrado_mes['perfil'].isin(['Saída de Caixa', 'Entrada de Caixa'])]
                if not df_sem_caixa.empty:
                    media_transacao = df_sem_caixa['valor'].mean()
                    transacoes_acima_media = df_sem_caixa[df_sem_caixa['valor'] > media_transacao * 1.5]
                    
                    if not transacoes_acima_media.empty:
                        st.warning(f"Transações acima de 50% da média: {len(transacoes_acima_media)}")
                        
                        # CSS personalizado para os cards
                        st.markdown("""
                        <style>
                        .card {
                            border-radius: 10px;
                            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                            padding: 15px;
                            margin-bottom: 15px;
                            background-color: #ffffff;
                            border-left: 5px solid #ff4b4b;
                        }
                        .card-title {
                            color: #333333;
                            font-weight: bold;
                            font-size: 16px;
                            margin-bottom: 8px;
                        }
                        .card-value {
                            color: #ff4b4b;
                            font-weight: bold;
                            font-size: 18px;
                            margin-bottom: 5px;
                        }
                        .card-detail {
                            color: #666666;
                            margin-bottom: 3px;
                            display: flex;
                        }
                        .card-label {
                            min-width: 100px;
                            font-weight: 500;
                        }
                        .percentage-high {
                            background-color: #ffeeee;
                            padding: 2px 8px;
                            border-radius: 10px;
                            color: #ff4b4b;
                            font-weight: bold;
                            display: inline-block;
                            margin-left: 8px;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        
                        # Botão para mostrar/ocultar transações acima da média
                        if "mostrar_transacoes_acima" not in st.session_state:
                            st.session_state.mostrar_transacoes_acima = False

                        button_text = "Ocultar transações acima da média" if st.session_state.mostrar_transacoes_acima else "Ver transações acima da média"
                        if st.button(button_text):
                            st.session_state.mostrar_transacoes_acima = not st.session_state.mostrar_transacoes_acima
                            st.rerun()

                        if st.session_state.mostrar_transacoes_acima:
                            st.subheader("Detalhes das transações acima da média")
                            
                            # Ordenar transações da mais alta para a mais baixa em relação à média
                            transacoes_ordenadas = transacoes_acima_media.sort_values(by='valor', ascending=False)
                            
                            for _, row in transacoes_ordenadas.iterrows():
                                usuario = row['usuario']
                                valor_formatado = formatar_valor(row['valor'])
                                valor_numerico = float(row['valor'])
                                percentual = (valor_numerico / media_transacao) * 100 - 100
                                data = row['data'].strftime('%d/%m/%Y') if hasattr(row['data'], 'strftime') else row['data']
                                perfil = row['perfil']
                                descricao = row['descricao'] if 'descricao' in row and row['descricao'] else "Sem descrição"
                                
                                # Card HTML para cada transação
                                st.markdown(f"""
                                <div class="card">
                                    <div class="card-title">Transação de {usuario}</div>
                                    <div class="card-value">{valor_formatado} <span class="percentage-high">{percentual:.1f}% da média</span></div>
                                    <div class="card-detail"><span class="card-label">Data:</span> {data}</div>
                                    <div class="card-detail"><span class="card-label">Categoria:</span> {perfil}</div>
                                    <div class="card-detail"><span class="card-label">Descrição:</span> {descricao}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # Resumo estatístico
                            st.markdown("### Resumo Estatístico")
                            col2, col3 = st.columns(2)
                            with col2:
                                st.metric("Maior transação", formatar_valor(transacoes_ordenadas['valor'].max()))
                            with col3:
                                st.metric("Total acima da média", formatar_valor(transacoes_ordenadas['valor'].sum()))

                # Ver detalhes de um usuário específico
                usuario_selecionado = st.selectbox("Ver detalhes de transações do usuário:", options=df_filtrado["Usuário"].tolist())
                
                # Sempre mostrar transações
                st.session_state['ver_transacoes'] = True
                
                if st.session_state.get('ver_transacoes', False):
                    st.subheader(f"Transações de {usuario_selecionado}")
                    
                    # Obter transações do usuário selecionado
                    transacoes_usuario = [t for t in todos_registros if t.get('usuario') == usuario_selecionado]
                    if transacoes_usuario:
                        df_transacoes = criar_dataframe_transacoes(transacoes_usuario)
                        # Filtros por mês e ano
                        meses = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                        ano_atual = datetime.now().year
                        anos_disponiveis = sorted(list(set([
                            x.split("/")[-1][:4] if '/' in x else str(ano_atual)
                            for x in df_transacoes["Data"].astype(str)
                        ])), reverse=True)
                        if not anos_disponiveis:
                            anos_disponiveis = [str(ano_atual)]
                        col_mes, col_ano = st.columns(2)
                        with col_mes:
                            mes_filtro_nome = st.selectbox("Filtrar por mês", meses, index=datetime.now().month, key="mes_filtro_usuario_sup")
                        with col_ano:
                            ano_filtro = st.selectbox("Filtrar por ano", anos_disponiveis, key="ano_filtro_usuario_sup")
                        df_filtrado_usuario = df_transacoes.copy()
                        # Filtro por ano
                        if ano_filtro:
                            df_filtrado_usuario = df_filtrado_usuario[df_filtrado_usuario['Data'].apply(lambda x: x.split('/')[-1][:4] == ano_filtro if '/' in x else False)]
                        # Filtro por mês
                        if mes_filtro_nome != "Todos":
                            mes_filtro = meses.index(mes_filtro_nome)
                            df_filtrado_usuario = df_filtrado_usuario[df_filtrado_usuario['Data'].apply(lambda x: int(x.split('/')[1]) == mes_filtro if '/' in x else False)]
                        # Exibir tabela de transações do usuário
                        if not df_filtrado_usuario.empty:
                            df_display = df_filtrado_usuario.copy()
                            df_display["Valor"] = df_display.apply(
                                lambda x: f"{x['Símbolo']} R$ {x['Valor_Display']}", axis=1
                            )
                            for index, row in df_display.iterrows():
                                col1, col1b, col2, col3, col4, col5, col6 = st.columns([1.5, 1, 2, 2, 3, 1, 1])
                                with col1:
                                    st.write(row["Data"].split(" ")[0])  # Data
                                with col1b:
                                    st.write(row["Hora"])  # Hora
                                with col2:
                                    st.write(row["Perfil"])
                                with col3:
                                    if row["Símbolo"] == "+":
                                        st.markdown(f"<span style='color:green'>+ R$ {row['Valor_Display']}</span>", unsafe_allow_html=True)
                                    else:
                                        st.markdown(f"<span style='color:red'>- R$ {row['Valor_Display']}</span>", unsafe_allow_html=True)
                                with col4:
                                    st.write(row["Descrição"])
                                with col5:
                                    st.write(row["Tipo"])
                                with col6:
                                    if row["Foto"] and os.path.exists(row["Foto"]):
                                        if st.button("📷", key=f"foto_sup_{row['ID']}_{index}"):
                                            st.session_state[f"mostrar_foto_sup_{row['ID']}"] = not st.session_state.get(f"mostrar_foto_sup_{row['ID']}", False)
                                            st.rerun()
                                if st.session_state.get(f"mostrar_foto_sup_{row['ID']}", False) and row["Foto"] and os.path.exists(row["Foto"]):
                                    st.image(row["Foto"], caption="Foto da transação", use_container_width=True)
                                    if st.button("Fechar foto", key=f"fechar_foto_sup_{row['ID']}_{index}"):
                                        st.session_state[f"mostrar_foto_sup_{row['ID']}"] = False
                                        st.rerun()
                                st.markdown("---")
                            # Mostrar saldo do período filtrado usando valores numéricos
                            try:
                                total_entradas = df_display[df_display["Tipo"] == "Entrada"]["Valor_Display"].apply(lambda v: float(str(v).replace('.', '').replace(',', '.'))).sum()
                                total_saidas = df_display[df_display["Tipo"] == "Saída"]["Valor_Display"].apply(lambda v: float(str(v).replace('.', '').replace(',', '.'))).sum()
                                saldo_periodo = total_entradas - total_saidas
                            except Exception as e:
                                total_entradas = 0.0
                                total_saidas = 0.0
                                saldo_periodo = 0.0
                            # Exibir saldos separados
                            st.subheader("Resumo do Período")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total de Entradas", f"R$ {total_entradas:.2f}".replace('.', ','))
                            with col2:
                                st.metric("Total de Saídas", f"R$ {total_saidas:.2f}".replace('.', ','))
                            with col3:
                                saldo_texto = f"R$ {saldo_periodo:.2f}".replace('.', ',')
                                if saldo_periodo >= 0:
                                    st.metric("Saldo do Período", saldo_texto)
                                else:
                                    st.metric("Saldo do Período", saldo_texto, delta_color="inverse")
                        else:
                            st.info("Nenhuma transação encontrada para este usuário no filtro selecionado.")
                        
                        # Exibir saldos separados do usuário selecionado
                        st.subheader("Saldos do Usuário")
                        saldos_usuario = obter_saldos_separados(usuario_selecionado)
                        col1, col2 = st.columns(2)
                        with col1:
                            saldo_colab = saldos_usuario['colaborador']
                            saldo_colab_fmt = formatar_valor(saldo_colab)
                            st.markdown("**Saldo do Colaborador:**")
                            if saldo_colab >= 0:
                                st.success(f"{saldo_colab_fmt}")
                            else:
                                st.error(f"{saldo_colab_fmt}")
                                st.info("💡 Este valor será devolvido pela empresa")
                        with col2:
                            saldo_emp = saldos_usuario['emprestado']
                            saldo_emp_fmt = formatar_valor(saldo_emp)
                            st.markdown("**Saldo Emprestado:**")
                            if saldo_emp >= 0:
                                st.warning(f"{saldo_emp_fmt}")
                                if saldo_emp > 0:
                                    st.info("💡 Este valor deve ser devolvido")
                            else:
                                st.error(f"{saldo_emp_fmt}")
                        
                        # Botão para download em CSV
                        df_exportar = df_filtrado_usuario.copy()    

                        # Separar Data e Hora em colunas diferentes
                        df_exportar["Data_Export"] = df_exportar["Data"].apply(lambda x: x.split(" ")[0] if " " in str(x) else str(x))
                        df_exportar["Hora_Export"] = df_exportar["Hora"]

                        # Converter valores para negativos ou positivos com base no tipo (usando coluna "Valor" original)
                        df_exportar["Valor_Num"] = df_exportar.apply(
                            lambda x: -converter_para_float(x["Valor"]) if x["Tipo"] == "Saída" else converter_para_float(x["Valor"]),
                            axis=1
                        )

                        # Buscar dados originais do banco para ter origem_saldo, status_caixa E valor
                        dados_originais = [t for t in todos_registros if t.get('usuario') == usuario_selecionado]
                        origens_dict = {t['id_transacao']: t.get('origem_saldo', 'colaborador') for t in dados_originais}
                        status_caixa_dict = {t['id_transacao']: t.get('status_caixa', '') for t in dados_originais}
                        valores_dict = {t['id_transacao']: t.get('valor', 0) for t in dados_originais}

                        df_exportar["Origem"] = df_exportar["ID"].map(origens_dict).fillna("colaborador")
                        df_exportar["Status_Caixa_Raw"] = df_exportar["ID"].map(status_caixa_dict).fillna("")
                        df_exportar["Valor_Original"] = df_exportar["ID"].map(valores_dict).fillna(0)

                        # Calcular saldo acumulado para detectar se Entrada de Caixa é abertura ou fechamento
                        df_temp = df_exportar.sort_values('Data_Ordenacao').copy()
                        saldo_acumulado = 0.0
                        status_caixa_dict = {}

                        for idx, row in df_temp.iterrows():
                            status_raw = row["Status_Caixa_Raw"]
                            perfil = row["Perfil"]
                            valor_original = converter_para_float(row["Valor_Original"])
                            origem = row["Origem"]
                            trans_id = row["ID"]
                            
                            status_formatado = ""
                            
                            if status_raw and status_raw != "" and origem == "colaborador":
                                try:
                                    # Converter data para formato brasileiro
                                    data_obj = datetime.strptime(str(status_raw)[:10], '%Y-%m-%d')
                                    data_br = data_obj.strftime('%d/%m/%Y')
                                    
                                    tol = 1e-9
                                    
                                    if perfil == "Entrada de Caixa":
                                        # Se saldo estava zerado antes da entrada = ABERTURA
                                        if abs(saldo_acumulado) < tol:
                                            status_formatado = f"Abertura: {data_br}"
                                        # Se saldo estava negativo e vai zerar = FECHAMENTO
                                        elif saldo_acumulado < -tol:
                                            saldo_apos = saldo_acumulado + valor_original
                                            if abs(saldo_apos) < tol:
                                                status_formatado = f"Fechamento: {data_br}"
                                            # Se não zera, considera abertura (caso de valor maior que o negativo)
                                            else:
                                                status_formatado = f"Abertura: {data_br}"
                                    elif perfil == "Saída de Caixa":
                                        # Saída de caixa sempre é fechamento
                                        status_formatado = f"Fechamento: {data_br}"
                                except:
                                    status_formatado = ""
                            
                            status_caixa_dict[trans_id] = status_formatado
                            
                            # Atualizar saldo acumulado
                            if origem == "colaborador":
                                if perfil == "Entrada de Caixa":
                                    saldo_acumulado += valor_original
                                else:
                                    saldo_acumulado -= valor_original

                        # Aplicar status_caixa de volta na ordem original
                        df_exportar["Status_Caixa"] = df_exportar["ID"].map(status_caixa_dict).fillna("")

                        # Separar valores conforme origem_saldo
                        df_exportar["Colaborador"] = df_exportar.apply(
                            lambda x: x["Valor_Num"] if x["Origem"] == "colaborador" else 0.0,
                            axis=1
                        )
                        df_exportar["Emprestado"] = df_exportar.apply(
                            lambda x: x["Valor_Num"] if x["Origem"] == "emprestado" else 0.0,
                            axis=1
                        )

                        # Arredondar valores para 2 casas decimais ANTES de somar
                        df_exportar["Colaborador"] = df_exportar["Colaborador"].round(2)
                        df_exportar["Emprestado"] = df_exportar["Emprestado"].round(2)

                        # Somatórios com arredondamento
                        total_colab = round(df_exportar["Colaborador"].sum(), 2)
                        total_emp = round(df_exportar["Emprestado"].sum(), 2)

                        # Forçar zero se valor for muito pequeno (erro de arredondamento)
                        if abs(total_colab) < 0.01:
                            total_colab = 0.0
                        if abs(total_emp) < 0.01:
                            total_emp = 0.0

                        # Selecionar colunas desejadas na ordem correta
                        df_final = df_exportar[["Data_Export", "Hora_Export", "Perfil", "Descrição", "Tipo", "Colaborador", "Emprestado", "Status_Caixa"]].copy()

                        # Renomear colunas para o CSV
                        df_final.columns = ["Data", "Hora", "Perfil", "Descrição", "Tipo", "Colaborador", "Emprestado", "Status do Caixa"]

                        # Adiciona linha de totais
                        df_totais = pd.DataFrame([{
                            "Data": "",
                            "Hora": "",
                            "Perfil": "",
                            "Descrição": "TOTAL",
                            "Tipo": "",
                            "Colaborador": total_colab,
                            "Emprestado": total_emp,
                            "Status do Caixa": ""
                        }])

                        df_final = pd.concat([df_final, df_totais], ignore_index=True)

                        # Criar CSV com encoding adequado
                        csv = df_final.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")

                        st.download_button(
                            label="📄 Baixar CSV das Transações",
                            data=csv,
                            file_name=f"transacoes_{usuario_selecionado}.csv",
                            mime="text/csv"
                        )
def calcular_saldo_colaborador_ate(usuario, data_limite_str):
    """
    Calcula o saldo do colaborador para 'usuario' considerando apenas transações
    com data STRICTAMENTE menor que data_limite_str (usa apenas a parte de data).
    Retorna float.
    """
    try:
        trans = obter_transacoes_usuario(usuario)
        # converter limite para date
        limite = extrair_data_para_date(data_limite_str)
        if limite is None:
            return 0.0
        saldo = 0.0
        # ordenar por data (asc)
        def key_dt(x):
            d = extrair_data_para_date(x.get('data') or "")
            return d or datetime.min.date()
        trans_sorted = sorted(trans, key=key_dt)
        for t in trans_sorted:
            d = extrair_data_para_date(t.get('data') or "")
            if d is None:
                continue
            if d < limite:
                origem = t.get('origem_saldo', 'colaborador')
                perfil_t = t.get('perfil', '')
                valor_t = obter_valor_numerico(t.get('valor', 0))
                if origem == 'colaborador':
                    if perfil_t == "Entrada de Caixa":
                        saldo += valor_t
                    else:
                        saldo -= valor_t
            else:
                break
        return saldo
    except:
        return 0.0

adicionar_rodape()
