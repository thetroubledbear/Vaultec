<script lang="ts">
  import { session } from '$lib/stores/session.svelte.ts';
  import { apiJson, ApiError } from '$lib/api';
  import Panel from '$lib/components/Panel.svelte';
  import StatCard from '$lib/components/StatCard.svelte';
  import Button from '$lib/components/Button.svelte';
  import Toast from '$lib/components/Toast.svelte';
  import Modal from '$lib/components/Modal.svelte';

  // Account Settings
  let currentPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let passwordLoading = $state(false);
  let passwordMessage = $state('');
  let passwordError = $state('');

  // Admin Stats
  interface AdminStats {
    user_count: number;
    active_user_count: number;
    document_count: number;
    category_count: number;
    household_count: number;
    vault_unlocked: boolean;
  }

  interface AdminUser {
    id: string;
    username: string;
    role: string;
    is_active: boolean;
    created_at: string;
    household_id?: string | null;
  }

  interface Household {
    id: string;
    name: string;
    member_count: number;
    created_at: string;
  }

  let stats = $state<AdminStats | null>(null);
  let users = $state<AdminUser[]>([]);
  let households = $state<Household[]>([]);
  let statsLoading = $state(false);
  let statsError = $state('');

  // User Management
  let showCreateUserModal = $state(false);
  let newUsername = $state('');
  let newPassword2 = $state('');
  let newRole = $state('admin');
  let newUserHouseholdId = $state<string | null>(null);
  let createUserLoading = $state(false);
  let createUserError = $state('');

  let editingUserId = $state<string | null>(null);
  let editingUsername = $state('');
  let editingRole = $state('');
  let editingHouseholdId = $state<string | null>(null);
  let editingActive = $state(false);
  let editLoading = $state(false);
  let editError = $state('');

  // Household Management
  let showCreateHouseholdModal = $state(false);
  let newHouseholdName = $state('');
  let createHouseholdLoading = $state(false);
  let createHouseholdError = $state('');

  async function handleChangePassword() {
    passwordError = '';
    passwordMessage = '';

    if (!currentPassword || !newPassword || !confirmPassword) {
      passwordError = 'All fields required';
      return;
    }

    if (newPassword !== confirmPassword) {
      passwordError = 'Passwords do not match';
      return;
    }

    if (newPassword.length < 8) {
      passwordError = 'New password must be at least 8 characters';
      return;
    }

    try {
      passwordLoading = true;
      await apiJson('/api/auth/change-password', 'POST', {
        current_password: currentPassword,
        new_password: newPassword
      });
      passwordMessage = 'Password changed successfully!';
      currentPassword = '';
      newPassword = '';
      confirmPassword = '';
      setTimeout(() => {
        passwordMessage = '';
      }, 3000);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        passwordError = 'Current password is incorrect';
      } else {
        passwordError = err instanceof Error ? err.message : 'Failed to change password';
      }
    } finally {
      passwordLoading = false;
    }
  }

  async function loadAdminData() {
    if (session.user?.role !== 'admin') return;

    try {
      statsLoading = true;
      statsError = '';
      const [statsRes, usersRes, householdsRes] = await Promise.all([
        apiJson<AdminStats>('/api/admin/stats', 'GET'),
        apiJson<AdminUser[]>('/api/admin/users', 'GET'),
        apiJson<Household[]>('/api/admin/households', 'GET')
      ]);
      stats = statsRes;
      users = usersRes || [];
      households = householdsRes || [];
    } catch (err) {
      statsError = err instanceof Error ? err.message : 'Failed to load admin data';
    } finally {
      statsLoading = false;
    }
  }

  $effect.pre(() => {
    if (session.isAuthenticated && session.user?.role === 'admin') {
      loadAdminData();
    }
  });

  async function handleCreateUser() {
    createUserError = '';

    if (!newUsername.trim() || !newPassword2.trim()) {
      createUserError = 'Username and password required';
      return;
    }

    if (newPassword2.length < 8) {
      createUserError = 'Password must be at least 8 characters';
      return;
    }

    try {
      createUserLoading = true;
      const payload: Record<string, unknown> = {
        username: newUsername.trim(),
        password: newPassword2,
        role: newRole
      };
      if (newUserHouseholdId) {
        payload.household_id = newUserHouseholdId;
      }
      await apiJson('/api/admin/users', 'POST', payload);
      newUsername = '';
      newPassword2 = '';
      newRole = 'admin';
      newUserHouseholdId = null;
      showCreateUserModal = false;
      await loadAdminData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        createUserError = 'User already exists';
      } else {
        createUserError = err instanceof Error ? err.message : 'Failed to create user';
      }
    } finally {
      createUserLoading = false;
    }
  }

  function startEditUser(user: AdminUser) {
    editingUserId = user.id;
    editingUsername = user.username;
    editingRole = user.role;
    editingHouseholdId = user.household_id || null;
    editingActive = user.is_active;
    editError = '';
  }

  async function saveUserEdit() {
    if (!editingUserId) return;

    editError = '';

    try {
      editLoading = true;
      const payload: Record<string, unknown> = {
        username: editingUsername,
        role: editingRole,
        is_active: editingActive
      };
      if (editingHouseholdId) {
        payload.household_id = editingHouseholdId;
      }
      await apiJson(`/api/admin/users/${editingUserId}`, 'PATCH', payload);
      editingUserId = null;
      await loadAdminData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        editError = err.detail || 'Cannot make this change (last admin guard)';
      } else {
        editError = err instanceof Error ? err.message : 'Failed to update user';
      }
    } finally {
      editLoading = false;
    }
  }

  function cancelEditUser() {
    editingUserId = null;
    editError = '';
  }

  async function handleDeleteUser(userId: string) {
    if (!confirm('Are you sure? This will deactivate the user.')) return;

    try {
      editLoading = true;
      await apiJson(`/api/admin/users/${userId}`, 'DELETE');
      await loadAdminData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        alert(err.detail || 'Cannot delete this user (last admin guard)');
      } else {
        alert(err instanceof Error ? err.message : 'Failed to delete user');
      }
    } finally {
      editLoading = false;
    }
  }

  async function handleCreateHousehold() {
    createHouseholdError = '';

    if (!newHouseholdName.trim()) {
      createHouseholdError = 'Household name required';
      return;
    }

    try {
      createHouseholdLoading = true;
      await apiJson('/api/admin/households', 'POST', {
        name: newHouseholdName.trim()
      });
      newHouseholdName = '';
      showCreateHouseholdModal = false;
      await loadAdminData();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        createHouseholdError = 'Household already exists';
      } else {
        createHouseholdError = err instanceof Error ? err.message : 'Failed to create household';
      }
    } finally {
      createHouseholdLoading = false;
    }
  }

  function getHouseholdName(householdId: string | null | undefined): string {
    if (!householdId) return 'None';
    const household = households.find(h => h.id === householdId);
    return household?.name || 'Unknown';
  }
</script>

<div class="max-w-6xl mx-auto px-4 py-8">
  <div class="mb-8 flex items-center gap-3">
    <h1 class="text-2xl uppercase font-bold tracking-widest text-bright glow-cyan">// SETTINGS</h1>
  </div>

  <!-- Account Settings Section -->
  <Panel title="ACCOUNT">
    <div class="max-w-md space-y-6">
      <div>
        <h3 class="label mb-4">Change Password</h3>

        {#if passwordError}
          <div class="mb-4 p-3 border border-danger text-danger text-sm">
            {passwordError}
          </div>
        {/if}

        {#if passwordMessage}
          <div class="mb-4 p-3 border border-success text-success text-sm">
            {passwordMessage}
          </div>
        {/if}

        <div class="space-y-4">
          <div>
            <div class="label mb-2">Current Password</div>
            <input
              type="password"
              bind:value={currentPassword}
              disabled={passwordLoading}
              class="input w-full text-sm disabled:opacity-50"
            />
          </div>

          <div>
            <div class="label mb-2">New Password</div>
            <input
              type="password"
              bind:value={newPassword}
              disabled={passwordLoading}
              class="input w-full text-sm disabled:opacity-50"
            />
          </div>

          <div>
            <div class="label mb-2">Confirm New Password</div>
            <input
              type="password"
              bind:value={confirmPassword}
              disabled={passwordLoading}
              class="input w-full text-sm disabled:opacity-50"
            />
          </div>

          <Button
            onclick={handleChangePassword}
            disabled={passwordLoading}
            variant="primary"
          >
            {passwordLoading ? 'UPDATING...' : '[ UPDATE PASSWORD ]'}
          </Button>
        </div>
      </div>
    </div>
  </Panel>

  <!-- Admin Section -->
  {#if session.user?.role === 'admin'}
    <!-- System Stats -->
    <Panel title="SYSTEM STATISTICS" class="mb-8">
      {#if statsError}
        <div class="mb-4 p-3 border border-danger text-danger text-sm">
          {statsError}
        </div>
      {/if}

      {#if statsLoading}
        <div class="text-center py-8 text-muted">
          <div class="inline-block animate-spin">⏳</div>
          <p class="mt-2">Loading statistics...</p>
        </div>
      {:else if stats}
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard label="Users" value={stats.user_count} accent="cyan" />
          <StatCard label="Active" value={stats.active_user_count} accent="cyan" />
          <StatCard label="Documents" value={stats.document_count} accent="cyan" />
          <StatCard label="Categories" value={stats.category_count} accent="cyan" />
          <StatCard label="Households" value={stats.household_count} accent="cyan" />
          <StatCard
            label="Vault"
            value={stats.vault_unlocked ? '🔓' : '🔒'}
            accent={stats.vault_unlocked ? 'success' : 'amber'}
          />
        </div>
      {/if}
    </Panel>

    <!-- User Management -->
    <Panel title="USER MANAGEMENT" class="mb-8">
      <div class="flex gap-3 mb-4">
        <Button
          onclick={() => (showCreateUserModal = true)}
          variant="primary"
        >
          + CREATE USER
        </Button>
      </div>

      {#if statsLoading}
        <div class="text-center py-8 text-muted">
          <div class="inline-block animate-spin">⏳</div>
          <p class="mt-2">Loading users...</p>
        </div>
      {:else if users.length === 0}
        <div class="text-center py-8 text-muted">
          No users found
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-xs font-mono">
            <thead>
              <tr class="border-b border-line">
                <th class="px-4 py-2 text-left label">Username</th>
                <th class="px-4 py-2 text-left label">Role</th>
                <th class="px-4 py-2 text-left label">Household</th>
                <th class="px-4 py-2 text-left label">Status</th>
                <th class="px-4 py-2 text-left label">Created</th>
                <th class="px-4 py-2 text-right label">Actions</th>
              </tr>
            </thead>
            <tbody>
              {#each users as user (user.id)}
                {#if editingUserId === user.id}
                  <tr class="border-b border-line bg-panel-light">
                    <td class="px-4 py-3">
                      <input
                        type="text"
                        bind:value={editingUsername}
                        disabled={editLoading}
                        class="input text-xs disabled:opacity-50"
                      />
                    </td>
                    <td class="px-4 py-3">
                      <select
                        bind:value={editingRole}
                        disabled={editLoading}
                        class="input text-xs disabled:opacity-50"
                      >
                        <option value="admin">admin</option>
                        <option value="member">member</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </td>
                    <td class="px-4 py-3">
                      <select
                        bind:value={editingHouseholdId}
                        disabled={editLoading}
                        class="input text-xs disabled:opacity-50"
                      >
                        <option value={null}>None</option>
                        {#each households as h (h.id)}
                          <option value={h.id}>{h.name}</option>
                        {/each}
                      </select>
                    </td>
                    <td class="px-4 py-3">
                      <label class="flex items-center gap-2">
                        <input
                          type="checkbox"
                          bind:checked={editingActive}
                          disabled={editLoading}
                          class="disabled:opacity-50"
                        />
                        <span class="text-xs text-muted">
                          {editingActive ? 'Active' : 'Inactive'}
                        </span>
                      </label>
                    </td>
                    <td class="px-4 py-3 text-muted">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td class="px-4 py-3 text-right">
                      <div class="flex items-center justify-end gap-1">
                        <Button
                          onclick={saveUserEdit}
                          disabled={editLoading}
                          variant="success"
                          size="sm"
                        >
                          Save
                        </Button>
                        <Button
                          onclick={cancelEditUser}
                          disabled={editLoading}
                          variant="ghost"
                          size="sm"
                        >
                          Cancel
                        </Button>
                      </div>
                      {#if editError}
                        <p class="mt-1 text-xs text-danger">{editError}</p>
                      {/if}
                    </td>
                  </tr>
                {:else}
                  <tr class="border-b border-line hover:bg-panel-light transition">
                    <td class="px-4 py-3 text-bright font-bold">
                      {user.username}
                    </td>
                    <td class="px-4 py-3 text-muted">
                      {user.role}
                    </td>
                    <td class="px-4 py-3 text-muted">
                      {getHouseholdName(user.household_id)}
                    </td>
                    <td class="px-4 py-3">
                      <span class={user.is_active ? 'text-success' : 'text-muted'}>
                        {user.is_active ? '✓ Active' : '✗ Inactive'}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-muted">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td class="px-4 py-3 text-right">
                      <div class="flex items-center justify-end gap-1">
                        <Button
                          onclick={() => startEditUser(user)}
                          variant="primary"
                          size="sm"
                        >
                          Edit
                        </Button>
                        <Button
                          onclick={() => handleDeleteUser(user.id)}
                          variant="danger"
                          size="sm"
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                {/if}
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </Panel>

    <!-- Households Management -->
    <Panel title="HOUSEHOLDS">
      <div class="flex gap-3 mb-4">
        <Button
          onclick={() => (showCreateHouseholdModal = true)}
          variant="primary"
        >
          + CREATE HOUSEHOLD
        </Button>
      </div>

      {#if households.length === 0}
        <div class="text-center py-8 text-muted">
          No households found
        </div>
      {:else}
        <div class="space-y-3">
          {#each households as household (household.id)}
            <div class="border border-line p-3 flex items-center justify-between">
              <div>
                <div class="text-bright font-bold">{household.name}</div>
                <div class="text-muted text-xs">{household.member_count} member{household.member_count !== 1 ? 's' : ''}</div>
              </div>
              <div class="text-muted text-xs">
                {new Date(household.created_at).toLocaleDateString()}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </Panel>
  {/if}
</div>

<!-- Create User Modal -->
<Modal title="CREATE NEW USER" open={showCreateUserModal} onClose={() => (showCreateUserModal = false)}>
  {#if createUserError}
    <div class="mb-4 p-3 border border-danger text-danger text-sm">
      {createUserError}
    </div>
  {/if}

  <div class="space-y-4">
    <div>
      <div class="label mb-2">Username</div>
      <input
        type="text"
        bind:value={newUsername}
        disabled={createUserLoading}
        placeholder="newuser"
        class="input w-full text-sm disabled:opacity-50"
      />
    </div>

    <div>
      <div class="label mb-2">Password</div>
      <input
        type="password"
        bind:value={newPassword2}
        disabled={createUserLoading}
        placeholder="min 8 characters"
        class="input w-full text-sm disabled:opacity-50"
      />
    </div>

    <div>
      <div class="label mb-2">Role</div>
      <select
        bind:value={newRole}
        disabled={createUserLoading}
        class="input w-full text-sm disabled:opacity-50"
      >
        <option value="admin">Admin</option>
        <option value="member">Member</option>
        <option value="viewer">Viewer</option>
      </select>
    </div>

    <div>
      <div class="label mb-2">Household (optional)</div>
      <select
        bind:value={newUserHouseholdId}
        disabled={createUserLoading}
        class="input w-full text-sm disabled:opacity-50"
      >
        <option value={null}>None</option>
        {#each households as h (h.id)}
          <option value={h.id}>{h.name}</option>
        {/each}
      </select>
    </div>

    <div class="flex gap-3 pt-4">
      <Button
        onclick={handleCreateUser}
        disabled={createUserLoading}
        variant="primary"
        full
      >
        {createUserLoading ? 'CREATING...' : '[ CREATE ]'}
      </Button>
      <Button
        onclick={() => (showCreateUserModal = false)}
        disabled={createUserLoading}
        variant="ghost"
        full
      >
        Cancel
      </Button>
    </div>
  </div>
</Modal>

<!-- Create Household Modal -->
<Modal title="CREATE HOUSEHOLD" open={showCreateHouseholdModal} onClose={() => (showCreateHouseholdModal = false)}>
  {#if createHouseholdError}
    <div class="mb-4 p-3 border border-danger text-danger text-sm">
      {createHouseholdError}
    </div>
  {/if}

  <div class="space-y-4">
    <div>
      <div class="label mb-2">Household Name</div>
      <input
        type="text"
        bind:value={newHouseholdName}
        disabled={createHouseholdLoading}
        placeholder="e.g., Smith Family"
        class="input w-full text-sm disabled:opacity-50"
      />
    </div>

    <div class="flex gap-3 pt-4">
      <Button
        onclick={handleCreateHousehold}
        disabled={createHouseholdLoading}
        variant="primary"
      >
        {createHouseholdLoading ? 'CREATING...' : '[ CREATE ]'}
      </Button>
      <Button
        onclick={() => (showCreateHouseholdModal = false)}
        disabled={createHouseholdLoading}
        variant="ghost"
      >
        Cancel
      </Button>
    </div>
  </div>
</Modal>
