# Factorized Steering Vector Geometry

Target: `transition`
Projected out: `hygiene, anti_meta, anti_stock`
Common layers: `[6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]`
Mean retained target norm: `0.827`

## Support Coefficients

| component | coefficient |
|---|---:|
| anchor | 0.250 |
| hygiene | 0.120 |
| anti_meta | 0.080 |
| anti_stock | 0.100 |

## Mean Layer-wise Cosine

| component | endpoint | transition | anchor | hygiene | anti_meta | anti_stock |
|---|---:|---:|---:|---:|---:|---:|
| endpoint | 1.000 | -0.358 | 0.432 | -0.652 | -0.782 | -0.579 |
| transition | -0.358 | 1.000 | 0.011 | 0.526 | 0.538 | 0.347 |
| anchor | 0.432 | 0.011 | 1.000 | -0.364 | -0.422 | -0.323 |
| hygiene | -0.652 | 0.526 | -0.364 | 1.000 | 0.899 | 0.602 |
| anti_meta | -0.782 | 0.538 | -0.422 | 0.899 | 1.000 | 0.657 |
| anti_stock | -0.579 | 0.347 | -0.323 | 0.602 | 0.657 | 1.000 |

## Projection By Layer

| layer | nuisance rank | retained target norm |
|---:|---:|---:|
| 6 | 3 | 0.678 |
| 7 | 3 | 0.735 |
| 8 | 3 | 0.772 |
| 9 | 3 | 0.797 |
| 10 | 3 | 0.810 |
| 11 | 3 | 0.852 |
| 12 | 3 | 0.862 |
| 13 | 3 | 0.868 |
| 14 | 3 | 0.898 |
| 15 | 3 | 0.910 |
| 16 | 3 | 0.919 |

## Interpretation Boundary

Layer-wise orthogonalization is an intervention on measured directions, not evidence that the named functions are causally independent in the model.
