import {
  createContext, useContext, useEffect, useState, ReactNode,
} from 'react'
import {
  User, onAuthStateChanged,
  signInWithPopup, signOut as firebaseSignOut,
} from 'firebase/auth'
import { doc, setDoc, getDoc, serverTimestamp } from 'firebase/firestore'
import { auth, db, googleProvider, isFirestoreConnectionIssue, markFirestoreUnavailable } from '../utils/firebase'

interface AuthContextValue {
  user: User | null
  loading: boolean
  isNewUser: boolean
  signInWithGoogle: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthCtx = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]         = useState<User | null>(null)
  const [loading, setLoading]   = useState(true)
  const [isNewUser, setIsNewUser] = useState(false)

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (u) => {
      setUser(u)
      setLoading(false)

      if (u) {
        try {
          const userRef = doc(db, 'users', u.uid)
          const snap = await getDoc(userRef)
          const existed = snap.exists()
          setIsNewUser(!existed)

          await setDoc(
            userRef,
            {
              uid:         u.uid,
              displayName: u.displayName,
              email:       u.email,
              photoURL:    u.photoURL,
              lastSeen:    serverTimestamp(),
              ...(existed ? {} : { createdAt: serverTimestamp() }),
            },
            { merge: true },
          )
        } catch (error) {
          if (isFirestoreConnectionIssue(error)) {
            markFirestoreUnavailable()
          } else {
            console.warn('Unable to sync Firebase user profile. Check Firestore rules/deployment.', error)
          }
          setIsNewUser(false)
        }
      }
    })
    return unsub
  }, [])

  const signInWithGoogle = async () => {
    await signInWithPopup(auth, googleProvider)
  }

  const signOut = async () => {
    setIsNewUser(false)
    await firebaseSignOut(auth)
  }

  return (
    <AuthCtx.Provider value={{ user, loading, isNewUser, signInWithGoogle, signOut }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
