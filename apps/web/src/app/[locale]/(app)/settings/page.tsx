import { Settings as SettingsIcon } from 'lucide-react'
import { getTranslations, setRequestLocale } from 'next-intl/server'

export default async function SettingsPage({
  params,
}: {
  params: { locale: string }
}) {
  const { locale } = params
  setRequestLocale(locale)
  const t = await getTranslations('Settings')
  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <SettingsIcon className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">{t('pageTitle')}</h1>
      </div>

      <section className="space-y-4">
        <div className="rounded-lg border border-border bg-canvas p-5">
          <h2 className="font-medium">{t('account.title')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('account.body')}</p>
        </div>
        <div className="rounded-lg border border-border bg-canvas p-5">
          <h2 className="font-medium">{t('openaiKey.title')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('openaiKey.body')}</p>
        </div>
        <div className="rounded-lg border border-border bg-canvas p-5">
          <h2 className="font-medium">{t('summarizer.title')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('summarizer.body')}</p>
        </div>
      </section>
    </main>
  )
}