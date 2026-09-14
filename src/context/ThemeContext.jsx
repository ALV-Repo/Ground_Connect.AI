import { createContext, useContext } from 'react'
const ThemeContext = createContext({ accent: '#4f46e5' })
export const useTheme = () => useContext(ThemeContext)
export const ThemeProvider = ThemeContext.Provider
