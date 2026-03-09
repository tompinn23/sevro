use crate::router::error::RadixMapError;
use crate::router::node::Node;
use crate::router::tokens::{common_prefix_bytes, tokenize, Token, TokenKind};
use std::collections::HashMap;


pub struct RadixMap<T> {
    root: Node<T>
}

impl<T> RadixMap<T> {
    pub fn new() -> Self {
        Self {
            root: Node::new("/")
        }
    }

    #[allow(dead_code)]
    pub fn insert(&mut self, path: &str, data: T) -> Result<Option<T>, RadixMapError> {
        let path = if path.len() > 1 && path.ends_with('/') {
            &path[..path.len() - 1]
        } else {
            path
        };
        let tokens = tokenize(path)?;
        let node = Self::insert_tokens(&mut self.root, &tokens)?;

        if let Some(value) = node.value.take() {
            node.value = Some(data);
            Ok(Some(value))
        } else {
            node.value = Some(data);
            Ok(None)
        }
    }

    pub fn get_mut_or_insert<F>(&mut self, pattern: &str, f: F) -> Result<&mut T, RadixMapError>
    where F: FnOnce() -> T,
    {
        let pattern = if pattern.len() > 1 && pattern.ends_with('/') {
            &pattern[..pattern.len() - 1]
        } else {
            pattern
        };
        let tokens = tokenize(pattern)?;
        let node = Self::insert_tokens(&mut self.root, &tokens)?;
        Ok(node.value.get_or_insert_with(f))
    }

    fn insert_tokens<'n>(
        node: &'n mut Node<T>,
        tokens: &[Token],
    ) -> Result<&'n mut Node<T>, RadixMapError> {
        let mut cur: *mut Node<T> = node;

        for token in tokens {
            //SAFETY: cur always points into the trie we don't share ownership,
            // this never actually holds two live &mut to the same node we always move down the
            // trie on each iteration
            //TODO: run miri
            cur = unsafe {
                match token.kind {
                    TokenKind::Static => Self::insert_static(&mut *cur, &token.value)?,
                    TokenKind::Param => Self::insert_param(&mut *cur, &token.value)?,
                    TokenKind::Wildcard => {
                        let n = Self::insert_wildcard(&mut *cur, &token.value)?;
                        return Ok(&mut *n);
                    }
                }
            };
        }

        Ok(unsafe { &mut *cur })
    }

    // run miri when changing this.
    fn insert_static(node: &mut Node<T>, val: &str) -> Result<*mut Node<T>, RadixMapError> {
        let mut val = val.as_bytes().to_vec();
        let mut cur: *mut Node<T> = node;

        loop {
            if val.is_empty() {
                return Ok(cur);
            }

            let node_ref = unsafe { &mut *cur };

            let mut best_idx: Option<usize> = None;
            let mut best_cpl = 0usize;
            for (i, child) in node_ref.static_children.iter().enumerate() {
                let cpl = common_prefix_bytes(&val, child.prefix.as_bytes());
                if cpl > best_cpl {
                    best_cpl = cpl;
                    best_idx = Some(i);
                }
            }

            return match best_idx {
                None => {
                    let leaf = Node::new(String::from_utf8(val).unwrap());
                    node_ref.static_children.push(leaf);
                    let idx = node_ref.static_children.len() - 1;
                    Ok(&mut node_ref.static_children[idx])
                }
                Some(idx) => {
                    let child_prefix_len = node_ref.static_children[idx].prefix.len();

                    if best_cpl == child_prefix_len && best_cpl == val.len() {
                        return Ok(&mut node_ref.static_children[idx]);
                    }

                    if best_cpl == child_prefix_len {
                        val = val[best_cpl..].to_vec();
                        cur = &mut node_ref.static_children[idx];
                        continue;
                    }

                    let common = String::from_utf8(val[..best_cpl].to_vec()).unwrap();
                    let remaining: Option<Vec<u8>> = if best_cpl < val.len() {
                        Some(val[best_cpl..].to_vec())
                    } else {
                        None
                    };
                    let existing_suffix = {
                        let b = node_ref.static_children[idx].prefix.as_bytes();
                        String::from_utf8(b[best_cpl..].to_vec()).unwrap()
                    };

                    let mut old_child = node_ref.static_children.remove(idx);
                    old_child.prefix = existing_suffix;

                    let mut mid = Node::new(common);
                    mid.static_children.push(old_child);

                    if let Some(rem) = remaining {
                        let new_leaf = Node::new(String::from_utf8(rem).unwrap());
                        mid.static_children.push(new_leaf);
                        node_ref.static_children.push(mid);
                        let mid_idx = node_ref.static_children.len() - 1;
                        let leaf_idx = node_ref.static_children[mid_idx].static_children.len() - 1;
                        Ok(&mut node_ref.static_children[mid_idx].static_children[leaf_idx])
                    } else {
                        node_ref.static_children.push(mid);
                        let mid_idx = node_ref.static_children.len() - 1;
                        Ok(&mut node_ref.static_children[mid_idx])
                    }
                }
            }
        }
    }

    fn insert_param(node: &mut Node<T>, name: &str) -> Result<*mut Node<T>, RadixMapError> {
        if node.param.is_none() {
            let mut child = Node::new("");
            child.param_name = Some(name.to_string());
            node.param = Some(Box::new(child));
        } else if node.param.as_ref().unwrap().param_name.as_deref() != Some(name) {
            return Err(RadixMapError::ConflictingParams(
                node.param.as_ref().unwrap().param_name.clone().unwrap_or("<none>".to_string()),
                name.to_string()
            ));
        }
        Ok(node.param.as_mut().unwrap().as_mut())
    }

    fn insert_wildcard(node: &mut Node<T>, name: &str) -> Result<*mut Node<T>, RadixMapError> {
        if node.wildcard.is_some() {
            if node.wildcard_name.as_deref() != Some(name) {
                return Err(RadixMapError::ConflictingWildcard(
                    node.wildcard_name.clone().unwrap_or("<none>".to_string()), name.to_string()
                ));
            }
            return Ok(node.wildcard.as_mut().unwrap().as_mut());
        }
        let mut child = Node::new("");
        child.wildcard_name = Some(name.to_string());
        node.wildcard = Some(Box::new(child));
        node.wildcard_name = Some(name.to_string());
        Ok(node.wildcard.as_mut().unwrap().as_mut())
    }

    pub fn get(&self, path: &str) -> Option<(&T, HashMap<String, String>)> {
        if !path.starts_with('/') {
            return None;
        }

        let path = if path.len() > 1 && path.ends_with('/') {
            &path[..path.len() - 1]
        } else {
            path
        };

        let mut remaining = &path[1..];
        let mut node = &self.root;
        let mut params: HashMap<String, String> = HashMap::new();

        loop {
            let static_match = node
                .static_children
                .iter()
                .find(|c| remaining.starts_with(c.prefix.as_str()));

            if let Some(child) = static_match {
                remaining = &remaining[child.prefix.len()..];
                node = child;
                continue;
            }

            if let Some(ref param_node) = node.param {
                let cut = remaining.find('/').unwrap_or(remaining.len());
                let seg = &remaining[..cut];
                remaining = &remaining[cut..];
                params.insert(param_node.param_name.clone().unwrap_or_default(), seg.to_string());
                node = param_node;
                continue;
            }

            if let Some(ref wc_node) = node.wildcard {
                params.insert(node.wildcard_name.clone().unwrap_or_default(), remaining.to_string());
                node = wc_node;
                remaining = "";
                break;
            }

            break;
        }

        if remaining.is_empty() {
            if let Some(ref value) = node.value {
                return Some((value, params));
            }
        }
        None
    }
}

impl<T> Default for RadixMap<T> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_map() -> RadixMap<&'static str> {
        let mut m = RadixMap::new();
        m.insert("/", "index").unwrap();
        m.insert("/about", "about").unwrap();
        m.insert("/users/:id", "user").unwrap();
        m.insert("/users/:id/posts/:post_id", "post").unwrap();
        m.insert("/files/*path", "file").unwrap();
        m
    }

    #[test]
    fn test_static_root() {
        let m = make_map();
        let (v, _) = m.get("/").unwrap();
        assert_eq!(*v, "index");
    }

    #[test]
    fn test_static_path() {
        let m = make_map();
        let (v, _) = m.get("/about").unwrap();
        assert_eq!(*v, "about");
    }

    #[test]
    fn test_param() {
        let m = make_map();
        let (v, p) = m.get("/users/42").unwrap();
        assert_eq!(*v, "user");
        assert_eq!(p["id"], "42");
    }

    #[test]
    fn test_nested_params() {
        let m = make_map();
        let (v, p) = m.get("/users/7/posts/99").unwrap();
        assert_eq!(*v, "post");
        assert_eq!(p["id"], "7");
        assert_eq!(p["post_id"], "99");
    }

    #[test]
    fn test_wildcard() {
        let m = make_map();
        let (v, p) = m.get("/files/a/b/c.txt").unwrap();
        assert_eq!(*v, "file");
        assert_eq!(p["path"], "a/b/c.txt");
    }

    #[test]
    fn test_no_match() {
        let m = make_map();
        assert!(m.get("/nonexistent").is_none());
    }

    #[test]
    fn test_duplicate_error() {
        let mut m: RadixMap<i32> = RadixMap::new();
        m.insert("/dup", 1).unwrap();
        assert_eq!(m.insert("/dup", 2).unwrap().unwrap(), 1);
    }

    #[test]
    fn test_any_t() {
        #[derive(Debug, PartialEq)]
        struct Config { timeout: u32 }

        let mut m: RadixMap<Config> = RadixMap::new();
        m.insert("/api/:version", Config { timeout: 30 }).unwrap();

        let (v, p) = m.get("/api/v2").unwrap();
        assert_eq!(v.timeout, 30);
        assert_eq!(p["version"], "v2");
    }

    #[test]
    fn test_tokenize_static() {
        let tokens = tokenize("/hello/world").unwrap();
        assert_eq!(tokens.len(), 1);
        assert_eq!(tokens[0].value, "hello/world");
    }

    #[test]
    fn test_tokenize_param() {
        let tokens = tokenize("/users/:id").unwrap();
        assert_eq!(tokens[0].kind, TokenKind::Static);
        assert_eq!(tokens[1].kind, TokenKind::Param);
        assert_eq!(tokens[1].value, "id");
    }

    #[test]
    fn test_tokenize_wildcard() {
        let tokens = tokenize("/files/*rest").unwrap();
        assert!(tokens.iter().any(|t| t.kind == TokenKind::Wildcard));
    }
}