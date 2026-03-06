use std::fmt::{Display, Formatter};
use hyper::http;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use hyper::http::uri::InvalidUri;
struct UriError(InvalidUri);

impl From<UriError> for PyErr {
    fn from(err: UriError) -> PyErr {
        PyValueError::new_err(err.0.to_string())
    }
}

impl From<InvalidUri> for UriError {
    fn from(err: InvalidUri) -> UriError {
        UriError(err)
    }
}

#[pyclass]
#[derive(Debug)]
struct URL {
    inner: http::Uri
}

impl Display for URL {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        self.inner.fmt(f)
    }
}

#[pymethods]
impl URL {
    #[new]
    fn py_new(uri: &str) -> Result<Self, UriError> {
        Ok(Self {
            inner: uri.parse::<http::Uri>()?,
        })
    }

    fn scheme(&self) -> Option<&str> {
        self.inner.scheme().map(|s| s.as_str())
    }

    fn host(&self) -> Option<&str> {
        self.inner.host()
    }

    fn path(&self) -> &str {
        self.inner.path()
    }

    fn port(&self) -> Option<u16> {
        self.inner.port_u16()
    }

    fn query_string(&self) -> Option<&str> {
        self.inner.query()
    }

    fn query<'a>(&self, py: Python<'a>) -> PyResult<Bound<'a, PyDict>> {
        let dict = PyDict::new(py);
        if let Some(query) = self.inner.query() {
            for (k, v) in form_urlencoded::parse(query.as_bytes()) {
                let k = k.as_ref();
                let v = v.as_ref();

                if let Some(existing) = dict.get_item(k)? {
                    let list: &Bound<PyList> = existing.cast()?;
                    list.append(v)?;
                } else {
                    let list = PyList::new(py, &[v])?;
                    dict.set_item(k, list)?;
                }
            }
        }
        Ok(dict)
    }

    fn __repr__(&self) -> String {
        self.to_string()
    }
}

pub(crate) fn configure(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<URL>()?;
    Ok(())
}