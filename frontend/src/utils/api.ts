import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { RecommendationResponse, Perfume, Stats, Category, FeaturedResponse, DescriptionResponse, ChatResponse } from '../types/index'
import { auth } from './firebase'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
const SHOULD_WAIT_FOR_BACKEND = API_BASE_URL.startsWith('/api') || API_BASE_URL.includes('localhost')

type ApiError = Error & {
  code?: string
  response?: { status?: number; data?: unknown }
  request?: unknown
  isOffline?: boolean
  isBackendUnavailable?: boolean
}

class APIClient {
  private client: AxiosInstance
  private backendReady: boolean = false
  private backendReadyPromise: Promise<boolean> | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: { 'Content-Type': 'application/json' },
      timeout: 30000,
    })

    /**
     * Request Interceptor
     * Attaches Firebase ID token to all requests for authentication
     */
    this.client.interceptors.request.use(
      async (config: InternalAxiosRequestConfig) => {
        if (SHOULD_WAIT_FOR_BACKEND) {
          const url = config.url || ''
          if (url !== '/health') {
            const ready = await this.ensureBackendReady()
            if (!ready) {
              const backendError = new Error(
                'Backend is still starting. Please try again in a moment.',
              ) as ApiError
              backendError.isBackendUnavailable = true
              return Promise.reject(backendError)
            }
          }
        }

        try {
          const currentUser = auth.currentUser
          if (currentUser) {
            const token = await currentUser.getIdToken()
            config.headers.Authorization = `Bearer ${token}`
          }
        } catch (error) {
          console.error('Failed to attach auth token:', error)
          // Continue without token if retrieval fails
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    /**
     * Response Interceptor
     * Handles errors and logs debug information
     */
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const apiError = error as ApiError

        if (!apiError.response) {
          const offline = typeof navigator !== 'undefined' && navigator.onLine === false
          apiError.isOffline = offline
          apiError.isBackendUnavailable = !offline

          if (apiError.code === 'ECONNABORTED') {
            apiError.message = 'The backend took too long to respond. Please try again in a moment.'
          } else if (offline) {
            apiError.message = 'You appear offline. Check your connection and try again.'
          } else {
            apiError.message = 'Cannot reach the backend right now. It may still be starting up or temporarily unavailable.'
          }
        } else {
          const status = apiError.response?.status

          if (status === 503) {
            // Backend is warming up — expected during startup, not a code error
            // Only log once at debug level; TopPicks handles retry silently
            console.debug('[API] Backend warming up (503) —', (error as any).config?.url)
          } else if (status === 429) {
            // Rate limit — log concisely
            console.warn('[API] Rate limited (429):', (error as any).config?.url)
          } else if (status === 500 && apiError.response?.data === '') {
            apiError.isBackendUnavailable = true
            apiError.message = 'The backend returned an empty error response. Make sure the FastAPI server is running.'
            console.warn('[API] Backend returned an empty 500:', (error as any).config?.url)
          } else {
            console.error('API Error:', {
              status,
              data: apiError.response?.data,
              url: (error as any).config?.url,
            })
          }
        }
        return Promise.reject(error)
      }
    )
  }

  private async ensureBackendReady(): Promise<boolean> {
    if (this.backendReady) return true
    if (!this.backendReadyPromise) {
      this.backendReadyPromise = this.waitUntilReady(1000, 180000)
        .then((ready) => {
          this.backendReady = ready
          return ready
        })
        .finally(() => {
          this.backendReadyPromise = null
        })
    }
    return this.backendReadyPromise
  }

  // Recommendations (public)
  async getRecommendations(
    preferences: string,
    num: number = 10,
    options: {
      preferred_gender?: string
      occasion?: string
      season?: string
      mood?: string
      liked_notes?: string[]
      disliked_notes?: string[]
      reference_perfumes?: string[]
      budget_min?: number
      budget_max?: number
    } = {},
  ): Promise<RecommendationResponse> {
    const res = await this.client.post('/recommendations', {
      preferences,
      num_recommendations: num,
      ...options,
    })
    return res.data
  }

  // Search
  async searchPerfumes(q: string, limit: number = 10): Promise<{ results: Perfume[] }> {
    const res = await this.client.get('/perfumes/search', { params: { q, limit } })
    return res.data
  }

  // Perfume detail
  async getPerfumeDetails(id: string): Promise<any> {
    const res = await this.client.get(`/perfumes/${id}`)
    return res.data
  }

  /**
   * Poll /health until the backend ML models are ready.
   * Uses /health (always 200) so no red network errors appear in the console.
   * Resolves as soon as status === "ready", or after maxWaitMs.
   */
  async waitUntilReady(intervalMs = 2000, maxWaitMs = 180000): Promise<boolean> {
    const deadline = Date.now() + maxWaitMs
    while (Date.now() < deadline) {
      try {
        const res = await this.client.get('/health', { timeout: 3000 })
        if (res.data?.status === 'ready') return true
      } catch {
        // backend not reachable yet — keep waiting
      }
      await new Promise(r => setTimeout(r, intervalMs))
    }
    return false
  }

  // Popular
  async getPopularPerfumes(limit: number = 8): Promise<{ popular: Perfume[] }> {
    const res = await this.client.get('/perfumes/popular', { params: { limit } })
    return res.data
  }

  async getFeaturedPerfumes(): Promise<FeaturedResponse> {
    const res = await this.client.get('/perfumes/featured')
    return res.data
  }

  // Categories
  async getCategories(): Promise<{ categories: Category[] }> {
    const res = await this.client.get('/perfumes/categories/list')
    return res.data
  }

  // Stats
  async getStats(): Promise<Stats> {
    const res = await this.client.get('/stats')
    return res.data
  }

  // Shopping Links
  async getShoppingLinks(name: string, brand: string, price: number = 0): Promise<any> {
    const res = await this.client.post('/ai/shopping-links', null, { 
      params: { perfume_name: name, brand, price }
    })
    return res.data
  }

  // Dynamic Image
  async getPerfumeImage(name: string, brand: string): Promise<{ image_url: string | null }> {
    const res = await this.client.get('/ai/perfume-image', { params: { perfume_name: name, brand } })
    return res.data
  }

  async enhancePerfumeDescription(
    perfumeId: string,
    currentDescription: string = '',
  ): Promise<DescriptionResponse> {
    const res = await this.client.get('/ai/perfume-description', {
      params: { perfume_id: perfumeId, current_description: currentDescription },
    })
    return res.data
  }

  // Conversational chat — with user context for personalization
  async chat(
    messages: Array<{ role: string; text: string; timestamp?: number }>,
    numRecommendations: number = 6,
    userContext?: {
      name?: string
      nickname?: string
      gender?: string
      dateOfBirth?: string
      preferredGender?: string
      favoriteNotes?: string[]
      preferredOccasion?: string
      preferredSeason?: string
      preferredIntensity?: string
      likedPerfumeNames?: string[]
      recentSearches?: string[]
      isNewUser?: boolean
      totalChats?: number
    },
  ): Promise<ChatResponse> {
    const res = await this.client.post('/ai/chat', {
      messages,
      num_recommendations: numRecommendations,
      user_context: userContext ?? null,
    })
    return res.data
  }

  // AI-powered chat (v2) — uses AI as PRIMARY decision engine
  async chatV2(
    messages: Array<{ role: string; text: string; timestamp?: number }>,
    numRecommendations: number = 6,
    userContext?: {
      name?: string
      nickname?: string
      gender?: string
      dateOfBirth?: string
      preferredGender?: string
      favoriteNotes?: string[]
      preferredOccasion?: string
      preferredSeason?: string
      preferredIntensity?: string
      likedPerfumeNames?: string[]
      recentSearches?: string[]
      isNewUser?: boolean
      totalChats?: number
    },
  ): Promise<ChatResponse> {
    const res = await this.client.post('/ai/chat-v2', {
      messages,
      num_recommendations: numRecommendations,
      user_context: userContext ?? null,
    })
    return res.data
  }
}

export const apiClient = new APIClient()
