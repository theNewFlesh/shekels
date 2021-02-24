from typing import Any, List

from lunchbox.enforce import Enforce, EnforceError
from pandas import DataFrame
# ------------------------------------------------------------------------------


def enforce_dataframes_are_equal(a, b):
    '''
    Endsures that DataFrames a and b have equal contents.

    Args:
        a (DataFrame): DataFrame A.
        b (DataFrame): DataFrame B.

    Raises:
        EnforceError: If a and b are not equal.
    '''
    # column names
    a_cols = set(a.columns.tolist())
    b_cols = b.columns.tolist()
    diff = a_cols.symmetric_difference(b_cols)
    diff = sorted(list(diff))

    msg = f'A and b have different columns: {diff}.'
    Enforce(len(diff), '==', 0, message=msg)

    # shape
    msg = 'A and b have different shapes. {a} != {b}.'
    Enforce(a.shape, '==', b.shape, message=msg)

    # NaNs cannot be compared
    a = a.fillna('---NAN---')
    b = b.fillna('---NAN---')

    # values
    errors = []
    for col in a.columns:
        mask = a[col] != b[col]
        a_vals = a.loc[mask, col].tolist()
        if len(a_vals) > 0:
            b_vals = b.loc[mask, col].tolist()
            error = [[col, av, bv] for av, bv in zip(a_vals, b_vals)]
            errors.extend(error)

    if len(errors) > 0:
        msg = DataFrame(errors, columns=['column', 'a', 'b']).to_string()
        msg = f'DatFrames have different values:\n{msg}'
        raise EnforceError(msg)

    #  records
    a = a.to_dict(orient='records')
    b = b.to_dict(orient='records')
    Enforce(a, '==', b)


def enforce_columns_in_dataframe(columns, data):
    # type: (List[str], DataFrame) -> None
    '''
    Ensure all given columns are in given dataframe columns.

    Args:
        columns (list[str]): Column names.
        data (DataFrame): DataFrame.

    Raises:
        EnforceError: If any column not found in data.columns.
    '''
    cols = data.columns.tolist()
    diff = set(columns).difference(cols)  # type: Any
    diff = sorted(list(diff))
    msg = f'Given columns not found in data. {diff} not in {cols}.'
    Enforce(diff, '==', [], message=msg)
