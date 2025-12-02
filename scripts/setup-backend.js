#!/usr/bin/env node

import { execSync } from 'child_process';
import { platform } from 'os';
import { join, resolve } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const backendDir = resolve(__dirname, '..', 'backend');
const venvDir = join(backendDir, '.venv');
const isWindows = platform() === 'win32';

/**
 * Find the correct uv command
 */
function findUvCommand() {
  try {
    execSync('uv --version', { stdio: 'ignore' });
    return 'uv';
  } catch (e) {
    if (!isWindows) {
      try {
        execSync('python3 -m uv --version', { stdio: 'ignore' });
        return 'python3 -m uv';
      } catch (e2) {
        console.error('❗ uv not found. Install uv: pip install --user uv');
        process.exit(1);
      }
    } else {
      try {
        execSync('py -m uv --version', { stdio: 'ignore' });
        return 'py -m uv';
      } catch (e2) {
        console.error('❗ uv not found. Install uv: pip install --user uv');
        process.exit(1);
      }
    }
  }
}

/**
 * Get the Python executable from the venv
 */
function getVenvPython() {
  if (isWindows) {
    return join(venvDir, 'Scripts', 'python.exe');
  } else {
    return join(venvDir, 'bin', 'python');
  }
}

/**
 * Create virtual environment
 */
function createVenv() {
  // Check if venv already exists
  const pythonPath = getVenvPython();
  if (existsSync(pythonPath)) {
    console.log('Virtual environment already exists, skipping creation...');
    return;
  }
  
  const uvCmd = findUvCommand();
  
  console.log('Creating virtual environment...');
  try {
    // Split command into parts for proper execution
    const cmdParts = uvCmd.split(' ');
    cmdParts.push('venv', '.venv');
    
    execSync(cmdParts.join(' '), {
      cwd: backendDir,
      stdio: 'inherit',
      shell: true
    });
    console.log('✅ Virtual environment created successfully!');
  } catch (error) {
    console.error('❌ Failed to create virtual environment');
    console.error('Error details:', error.message);
    process.exit(1);
  }
}

/**
 * Install requirements using uv pip
 */
function installRequirements() {
  const uvCmd = findUvCommand();
  const requirementsFile = join(backendDir, 'requirements.txt');
  const pythonPath = getVenvPython();
  
  // Verify venv exists
  if (!existsSync(pythonPath)) {
    console.error('❌ Virtual environment not found. Please create it first.');
    process.exit(1);
  }
  
  console.log('Installing requirements...');
  try {
    // Use uv pip install with the venv Python path
    // The --python flag should point to the Python executable in the venv
    const cmd = `${uvCmd} pip install -r "${requirementsFile}" --python "${pythonPath}"`;
    execSync(cmd, {
      cwd: backendDir,
      stdio: 'inherit',
      shell: true
    });
    console.log('✅ Requirements installed successfully!');
  } catch (error) {
    console.error('❌ Failed to install requirements');
    console.error('\nPossible causes:');
    console.error('1. Package compatibility issue (e.g., asyncpg may not support Python 3.13 yet)');
    console.error('2. Missing build dependencies (e.g., C compiler, Python headers)');
    console.error('\nSuggested solutions:');
    console.error('- Try using Python 3.11 or 3.12 instead of 3.13');
    console.error('- Update packages to newer versions that support Python 3.13');
    console.error('- Install build dependencies: xcode-select --install (macOS)');
    console.error('\nError details:', error.message);
    process.exit(1);
  }
}

// Main execution
try {
  createVenv();
  installRequirements();
  console.log('✅ Backend setup complete!');
} catch (error) {
  console.error('❌ Setup failed:', error.message);
  process.exit(1);
}

