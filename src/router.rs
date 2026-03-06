use crate::router::radix::RadixMap;
use pyo3::prelude::{PyModule, PyModuleMethods};
use pyo3::{pyclass, pymethods, Bound, Py, PyAny, PyResult, Python};
use std::collections::HashMap;

mod node;
mod tokens;
mod radix;
mod error;

#[pyclass]
pub struct Router {
    map: RadixMap<HashMap<String, Py<PyAny>>>
}

impl Router {
    fn single_route(&mut self, py: Python<'_>, path: &str, method: String, handler: Py<PyAny>) {
        if let Ok(handlers) = self.map.get_mut_or_insert(path, || HashMap::new()) {
            handlers.insert(method, handler.clone_ref(py));
        }
    }
}

#[pymethods]
impl Router {
    #[new]
    fn py_new() -> Self {
        Self {
            map: RadixMap::new()
        }
    }

    fn route(&mut self, py: Python<'_>, methods: Vec<String>, path: &str, handler: Py<PyAny>) {
        if let Ok(handlers) = self.map.get_mut_or_insert(path, || HashMap::new()) {
            for method in methods {
                handlers.insert(method, handler.clone_ref(py));
            }
        }
    }

    fn get(&mut self, py: Python<'_>, path: &str, handler: Py<PyAny>) {
        self.single_route(py, path, "GET".to_string(), handler);
    }
    fn post(&mut self, py: Python<'_>, path: &str, handler: Py<PyAny>) {
        self.single_route(py, path, "POST".to_string(), handler);
    }
    fn put(&mut self, py: Python<'_>, path: &str, handler: Py<PyAny>) {
        self.single_route(py, path, "PUT".to_string(), handler);
    }
    fn delete(&mut self, py: Python<'_>, path: &str, handler: Py<PyAny>) {
        self.single_route(py, path, "DELETE".to_string(), handler);
    }
    fn patch(&mut self, py: Python<'_>, path: &str, handler: Py<PyAny>) {
        self.single_route(py, path, "PATCH".to_string(), handler);
    }
    fn head(&mut self, py: Python<'_>, path: &str, handler: Py<PyAny>) {
        self.single_route(py, path, "HEAD".to_string(), handler);
    }
    fn options(&mut self, py: Python<'_>, path: &str, handler: Py<PyAny>) {
        self.single_route(py, path, "OPTIONS".to_string(), handler);
    }

    fn find(&self, py: Python<'_>, path: &str, method: &str) -> PyResult<Option<(Py<PyAny>, HashMap<String, String>)>> {
        match self.map.get(path) {
            Some((handlers, params)) => match handlers.get(method) {
                Some(handler) => Ok(Some((handler.clone_ref(py), params))),
                None => Ok(None),
            },
            None => Ok(None),
        }
    }
}

pub fn configure(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Router>()?;

    Ok(())
}
