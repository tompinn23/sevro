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

#[pymethods]
impl Router {
    #[new]
    fn py_new() -> Self {
        Self {
            map: RadixMap::new()
        }
    }

    fn route(&mut self, py: Python<'_>, method: &str, path: &str, handler: Py<PyAny>) {
        if let Ok(handlers) = self.map.get_mut_or_insert(path, || HashMap::new()) {
            handlers.insert(method.to_string(), handler.clone_ref(py));
        }
    }

    fn find(&self, py: Python<'_>, method: &str, path: &str) -> PyResult<Option<(Py<PyAny>, HashMap<String, String>)>> {
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
