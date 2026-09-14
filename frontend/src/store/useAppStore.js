import { create } from 'zustand'
import { api } from '../lib/api'

export const useAppStore = create((set, get) => ({
  farms: [],
  houses: [],
  currentFarmId: null,
  currentHouseId: null,
  isBootstrapped: false,
  needsOnboarding: false,
  pendingInvitations: [],
  isLoading: false,
  error: null,

  async bootstrap() {
    set({ isLoading: true, error: null })
    try {
      const farms = await api.farms.list()
      if (farms.length === 0) {
        // Before sending a brand-new user through farm creation, check
        // whether they were actually invited onto an existing farm -
        // team.myInvitations() is a collection-group lookup by their own
        // verified email, so this never leaks another org's invitations.
        const pendingInvitations = await api.team.myInvitations().catch(() => [])
        set({
          farms: [],
          houses: [],
          needsOnboarding: true,
          pendingInvitations,
          isBootstrapped: true,
          isLoading: false,
        })
        return
      }
      const currentFarmId = farms[0].id
      const houses = await api.houses.list(currentFarmId)
      set({
        farms,
        houses,
        currentFarmId,
        currentHouseId: houses[0]?.id ?? null,
        needsOnboarding: false,
        pendingInvitations: [],
        isBootstrapped: true,
        isLoading: false,
      })
    } catch (err) {
      set({ error: err.message, isLoading: false, isBootstrapped: true })
    }
  },

  async selectFarm(farmId) {
    set({ currentFarmId: farmId, isLoading: true })
    const houses = await api.houses.list(farmId)
    set({ houses, currentHouseId: houses[0]?.id ?? null, isLoading: false })
  },

  selectHouse(houseId) {
    set({ currentHouseId: houseId })
  },

  async refreshHouses() {
    const { currentFarmId } = get()
    if (!currentFarmId) return
    const houses = await api.houses.list(currentFarmId)
    set({ houses })
  },

  reset() {
    set({
      farms: [],
      houses: [],
      currentFarmId: null,
      currentHouseId: null,
      isBootstrapped: false,
      needsOnboarding: false,
      pendingInvitations: [],
      isLoading: false,
      error: null,
    })
  },
}))
