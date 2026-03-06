mod router;
mod url;

use pyo3::prelude::*;

#[pymodule(gil_used = false)]
fn core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    router::configure(m)?;
    url::configure(m)?;

    Ok(())
}