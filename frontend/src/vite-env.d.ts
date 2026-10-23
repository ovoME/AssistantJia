/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 前端是否启用 mock 数据；不设置或不为 'false' 时走 mock */
  readonly VITE_USE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
