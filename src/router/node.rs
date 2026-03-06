pub struct Node<T> {
    pub(crate) prefix: String,
    pub(crate) static_children: Vec<Node<T>>,
    pub(crate) param: Option<Box<Node<T>>>,
    pub(crate) param_name: Option<String>,
    pub(crate) wildcard: Option<Box<Node<T>>>,
    pub(crate) wildcard_name: Option<String>,
    pub(crate) value: Option<T>,
}

impl<T> Node<T> {
    pub(crate) fn new(prefix: impl Into<String>) -> Self {
        Self {
            prefix: prefix.into(),
            static_children: Vec::new(),
            param: None,
            param_name: None,
            wildcard: None,
            wildcard_name: None,
            value: None,
        }
    }
}