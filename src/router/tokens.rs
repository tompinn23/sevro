use crate::router::error::RadixMapError;

#[derive(Debug, Clone, PartialEq)]
pub(crate) enum TokenKind {
    Static,
    Param,
    Wildcard,
}

#[derive(Debug, Clone)]
pub(crate) struct Token {
    pub kind: TokenKind,
    pub value: String,
}

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------

pub(crate) fn tokenize(pattern: &str) -> Result<Vec<Token>, RadixMapError> {
    if !pattern.starts_with('/') {
        return Err(RadixMapError::MustBeginSlash);
    }

    let s = &pattern[1..];
    let chars: Vec<char> = s.chars().collect();
    let n = chars.len();
    let mut out = Vec::new();
    let mut buf = String::new();
    let mut i = 0;

    while i < n {
        match chars[i] {
            ':' => {
                if !buf.is_empty() {
                    out.push(Token { kind: TokenKind::Static, value: buf.clone() });
                    buf.clear();
                }
                let j_start = i + 1;
                let mut j = j_start;
                while j < n && chars[j] != '/' {
                    j += 1;
                }
                if j == j_start {
                    return Err(RadixMapError::EmptyParam);
                }
                let param_name: String = chars[j_start..j].iter().collect();
                out.push(Token { kind: TokenKind::Param, value: param_name });
                i = j;
            }
            '*' => {
                if !buf.is_empty() {
                    out.push(Token { kind: TokenKind::Static, value: buf.clone() });
                    buf.clear();
                }
                let rest: String = chars[i + 1..].iter().collect();
                if rest.contains('/') || rest.is_empty() {
                    return Err(RadixMapError::InvalidWildcard(rest));
                }
                out.push(Token { kind: TokenKind::Wildcard, value: rest });
                return Ok(out);
            }
            c => {
                buf.push(c);
                i += 1;
            }
        }
    }

    if !buf.is_empty() {
        out.push(Token { kind: TokenKind::Static, value: buf });
    }
    if out.is_empty() {
        out.push(Token { kind: TokenKind::Static, value: String::new() });
    }

    Ok(out)
}

pub fn common_prefix_bytes(a: &[u8], b: &[u8]) -> usize {
    a.iter().zip(b.iter()).take_while(|(x, y)| x == y).count()
}