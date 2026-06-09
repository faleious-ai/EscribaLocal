import re
from typing import List, Dict, Any

AUDIO_KEYWORDS = {
    "ideias": [
        "acho", "ideia", "pensei", "sugiro", "reunião", "projeto", "desenvolvimento", "criar", "fazer", "sugestão",
        "planejar", "inovação", "discussão", "opinião", "conceito", "testar"
    ],
    "decisoes": [
        "decidido", "definido", "concluído", "aprovado", "rejeitado", "prazo", "data", "entregável", "responsável",
        "fechado", "acordo", "definimos", "decidimos", "escolhido"
    ],
    "destaques": [
        "melhor", "pior", "importante", "crítico", "urgente", "sucesso", "erro", "falha", "atenção", "destaque",
        "principal", "prioridade", "problema", "risco", "alerta"
    ],
    "tarefas": [
        "combinamos", "tarefa", "entregar", "fazer", "próxima", "semana", "continuar", "reunião", "amanhã", "enviar",
        "agendar", "fazer", "responsabilidade", "ficar", "pendente"
    ]
}

def extract_audio_insights(segments: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Analisa os segmentos transcritos e extrai frases relevantes usando heurísticas
    de palavras-chave para auxiliar no resumo do áudio.
    """
    insights = {
        "ideias": [],
        "decisoes": [],
        "destaques": [],
        "tarefas": []
    }
    
    for seg in segments:
        text = seg["text"]
        text_lower = text.lower()
        
        for category, keywords in AUDIO_KEYWORDS.items():
            for kw in keywords:
                if re.search(r'\b' + kw + r'\b', text_lower):
                    time_str = f"[{format_time(seg['start'])}]"
                    formatted_sentence = f"{time_str} {text}"
                    if formatted_sentence not in insights[category]:
                        insights[category].append(formatted_sentence)
                    break
                    
    return insights

def format_time(seconds: float) -> str:
    """Converte segundos em formato MM:SS ou HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def generate_structured_minutes(segments: List[Dict[str, Any]]) -> str:
    """Gera uma ata de áudio estruturada baseada nos insights extraídos"""
    insights = extract_audio_insights(segments)
    
    draft = []
    draft.append("### ATA DE ÁUDIO ESTRUTURADA")
    draft.append("*(Destaques extraídos automaticamente das ideias e decisões identificadas)*")
    
    draft.append("\n**1. IDEIAS, CONCEITOS E BRAINSTORMS (Discussões e propostas):**")
    if insights["ideias"]:
        draft.extend([f"- {s}" for s in insights["ideias"][:6]])
    else:
        draft.append("- [Nenhuma frase-chave de ideias detectada automaticamente]")

    draft.append("\n**2. DECISÕES E ACORDOS (O que foi acordado/aprovado):**")
    if insights["decisoes"]:
        draft.extend([f"- {o}" for o in insights["decisoes"][:6]])
    else:
        draft.append("- [Nenhuma decisão expressa ou prazo final detectados automaticamente]")

    draft.append("\n**3. DESTAQUES E PONTOS CRÍTICOS (Riscos, erros ou prioridades):**")
    if insights["destaques"]:
        draft.extend([f"- {a}" for a in insights["destaques"][:6]])
    else:
        draft.append("- [Nenhum destaque crítico ou urgência detectada automaticamente]")

    draft.append("\n**4. PLANO DE AÇÃO E TAREFAS (Próximos passos e responsáveis):**")
    if insights["tarefas"]:
        draft.extend([f"- {p}" for p in insights["tarefas"][:6]])
    else:
        draft.append("- [Sem tarefas marcadas. Registre aqui as pendências acordadas]")
        
    return "\n".join(draft)

def generate_narrative_summary(segments: List[Dict[str, Any]]) -> str:
    """Gera um resumo executivo narrativo do áudio"""
    insights = extract_audio_insights(segments)
    
    draft = []
    draft.append("### RESUMO EXECUTIVO NARRATIVO")
    draft.append("*(Estrutura de síntese geral do áudio)*")
    
    draft.append("\n1. **TEMAS E TÓPICOS CENTRAIS:**")
    draft.append("- [Descreva resumidamente os principais assuntos tratados no áudio]")
    
    draft.append("\n2. **CONTEXTO E OBSERVAÇÕES DESTACADAS:**")
    if insights["ideias"]:
        draft.append("Aspectos e discussões levantadas:")
        draft.extend([f"  * {s}" for s in insights["ideias"][:4]])
    else:
        draft.append("- [Descreva o contexto geral da gravação...]")
         
    draft.append("\n3. **MOMENTOS IMPORTANTES E ALERTAS:**")
    if insights["destaques"]:
        draft.append("Pontos de destaque identificados:")
        draft.extend([f"  * {a}" for a in insights["destaques"][:3]])
    else:
        draft.append("- [Registre pontos relevantes discutidos...]")
        
    draft.append("\n4. **CRONOGRAMA E PRÓXIMOS ENCONTROS:**")
    if insights["tarefas"]:
        draft.extend([f"- {p}" for p in insights["tarefas"][:4]])
    else:
        draft.append("- Sem tarefas ou prazos imediatos agendados.")
        
    return "\n".join(draft)
