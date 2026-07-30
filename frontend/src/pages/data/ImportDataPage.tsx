import { useNavigate } from 'react-router-dom'

import { PageHeader } from '@/components/common/PageHeader'
import { ImportDatasetForm } from '@/features/datasets/components/ImportDatasetForm'
import { useImportDataset } from '@/features/datasets/queries'
import { getErrorMessage } from '@/lib/apiClient'

export default function ImportDataPage() {
  const navigate = useNavigate()
  const importDataset = useImportDataset()

  return (
    <div>
      <PageHeader
        title="Import market data"
        description="Upload OHLCV bars. CSV, Excel, and Parquet are supported."
      />

      <ImportDatasetForm
        isSubmitting={importDataset.isPending}
        onCancel={() => navigate('/data')}
        onSubmit={async (input) => {
          try {
            const dataset = await importDataset.mutateAsync(input)
            navigate(`/data/${dataset.id}`)
          } catch (error) {
            throw new Error(getErrorMessage(error, 'Import failed.'))
          }
        }}
      />
    </div>
  )
}
