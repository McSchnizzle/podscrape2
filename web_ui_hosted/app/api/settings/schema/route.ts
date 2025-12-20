import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const projectRoot = path.resolve(process.cwd(), '..')
    const scriptPath = path.join(projectRoot, 'scripts', 'export_settings_schema.py')
    const pythonPath = path.join(projectRoot, '.venv', 'bin', 'python3')

    return new Promise<NextResponse>((resolve) => {
      const python = spawn(pythonPath, [scriptPath], { cwd: projectRoot })
      let stdout = ''
      let stderr = ''

      python.stdout.on('data', (data: Buffer) => { stdout += data.toString() })
      python.stderr.on('data', (data: Buffer) => { stderr += data.toString() })

      python.on('close', (code: number) => {
        if (code !== 0) {
          console.error('Schema export failed:', stderr)
          resolve(NextResponse.json({ error: 'Schema export failed' }, { status: 500 }))
          return
        }
        try {
          const schema = JSON.parse(stdout)
          resolve(NextResponse.json(schema))
        } catch (e) {
          console.error('Invalid schema JSON:', e)
          resolve(NextResponse.json({ error: 'Invalid schema JSON' }, { status: 500 }))
        }
      })

      python.on('error', (error: Error) => {
        console.error('Failed to spawn Python process:', error)
        resolve(NextResponse.json({ error: 'Failed to spawn Python process' }, { status: 500 }))
      })
    })
  } catch (error) {
    console.error('Settings schema error:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
