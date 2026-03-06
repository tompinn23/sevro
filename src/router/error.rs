
#[derive(Debug, thiserror::Error)]
pub enum RadixMapError {
    #[error("paths must begin with a slash")]
    MustBeginSlash,
    #[error("empty param after ':'")]
    EmptyParam,
    #[error("invalid wildcard {0}")]
    InvalidWildcard(String),
    #[error("conflicting param name: {0} vs {1}")]
    ConflictingParams(String, String),
    #[error("conflicting wildcard name: {0} vs {1}")]
    ConflictingWildcard(String, String),
}

